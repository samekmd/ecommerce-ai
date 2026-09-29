"""API de ponta a ponta com TestClient: um event loop por cliente.

- Banco de negocio: sessao_escrita trocada pela versao com savepoint que
  sempre termina em rollback; nada fica gravado em loja.
- Auditoria: grava de verdade no app_db com um usuario unico por teste e
  e apagada no teardown.
- LLM: FunctionModel, sem rede.
"""

import base64
import uuid

import pytest
from fastapi.testclient import TestClient
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import FunctionModel
from sqlalchemy import text

from ops_agent.agente import agente as modulo_agente
from ops_agent.config import obter_configuracao
from ops_agent.database import sessao_app
from ops_agent.main import criar_app
from ops_agent.services import categoria, cupom, fornecedor, produto
from tests.conftest import rodar
from tests.unit.test_services import sessao_sem_commit

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
CNPJ_VALIDO = "11222333000181"


@pytest.fixture(scope="module", autouse=True)
def banco(banco_disponivel):
    return banco_disponivel


@pytest.fixture
def usuario():
    nome = f"teste-{uuid.uuid4().hex[:8]}"
    yield nome

    async def apagar():
        async with sessao_app() as sessao:
            await sessao.execute(text("DELETE FROM ops_cadastros WHERE usuario = :u"), {"u": nome})
            await sessao.execute(
                text("DELETE FROM ops_interpretacoes WHERE usuario = :u"), {"u": nome}
            )

    rodar(apagar())


@pytest.fixture
def cliente(monkeypatch):
    for modulo in (categoria, cupom, fornecedor, produto):
        monkeypatch.setattr(modulo, "sessao_escrita", sessao_sem_commit)
    with TestClient(criar_app(), raise_server_exceptions=False) as cliente:
        yield cliente


def consultar(cliente, sql: str, **parametros):
    """Roda no loop do TestClient: engines async nao atravessam loops."""

    async def _consultar():
        async with sessao_app() as sessao:
            return (await sessao.execute(text(sql), parametros)).mappings().all()

    return cliente.portal.call(_consultar)


def modelo_fixo(tool: str, **args):
    return FunctionModel(lambda mensagens, info: ModelResponse(parts=[ToolCallPart(tool, args)]))


def produto_json(**campos):
    dados = {
        "nome": "Camisa teste",
        "sku": f"TST-{uuid.uuid4().hex[:8]}",
        "preco": "100.00",
        "estoque": 5,
        "categoria_id": 1,
        "fornecedor_id": 1,
        "imagem": {"conteudo_base64": base64.b64encode(PNG).decode()},
    }
    return dados | campos


# --- saude --------------------------------------------------------------


def test_health_e_ready(cliente):
    assert cliente.get("/health").json() == {"status": "ok"}
    ready = cliente.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["bancos"] == {"leitura": True, "escrita": True, "app": True}


# --- interpretar --------------------------------------------------------


def test_interpretar_devolve_proposta_e_audita(cliente, usuario, monkeypatch):
    monkeypatch.setattr(
        modulo_agente,
        "obter_modelo",
        lambda: modelo_fixo("propor_produto", nome="Camisa", preco=100, avisos=["Sem fornecedor"]),
    )

    resposta = cliente.post(
        "/api/v1/interpretar", json={"mensagem": "Camisa a 100 reais"}, headers={"X-Usuario": usuario}
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["tipo"] == "produto"
    assert corpo["avisos"] == ["Sem fornecedor"]
    linhas = consultar(
        cliente,
        "SELECT tipo, proposta, erro, trace_id, prompt_versao FROM ops_interpretacoes WHERE id = :id",
        id=uuid.UUID(corpo["interpretacao_id"]),
    )
    assert linhas[0]["tipo"] == "produto"
    assert linhas[0]["proposta"]["preco"] == "100"
    assert linhas[0]["erro"] is None
    # Tracing desligado nos testes: sem trace e com o prompt embutido.
    assert linhas[0]["trace_id"] is None
    assert linhas[0]["prompt_versao"] is None


def test_interpretar_agente_falha_502_e_audita_erro(cliente, usuario, monkeypatch):
    monkeypatch.setattr(
        modulo_agente, "obter_modelo",
        lambda: modelo_fixo("propor_produto", nome="Camisa", fornecedor_id=999_999),
    )

    resposta = cliente.post(
        "/api/v1/interpretar", json={"mensagem": "Camisa"}, headers={"X-Usuario": usuario}
    )

    assert resposta.status_code == 502
    linhas = consultar(cliente, "SELECT tipo, erro FROM ops_interpretacoes WHERE usuario = :u", u=usuario)
    assert linhas == [{"tipo": None, "erro": "retries_esgotados"}]


def test_sem_x_usuario_422(cliente):
    resposta = cliente.post("/api/v1/interpretar", json={"mensagem": "x"})
    assert resposta.status_code == 422
    assert resposta.json()["erros"][0]["campo"] == "X-Usuario"


# --- cadastro -----------------------------------------------------------


def test_cadastrar_produto_audita_sem_bytes_da_imagem(cliente, usuario):
    interpretacao = uuid.uuid4()  # inexistente: a auditoria grava sem o vinculo
    resposta = cliente.post(
        "/api/v1/produtos",
        json=produto_json(),
        headers={"X-Usuario": usuario, "X-Interpretacao-Id": str(interpretacao)},
    )

    assert resposta.status_code == 201, resposta.text
    assert resposta.json()["id"] > 0
    linha = consultar(
        cliente,
        "SELECT resultado, entidade_id, payload, interpretacao_id FROM ops_cadastros WHERE usuario = :u",
        u=usuario,
    )[0]
    assert linha["resultado"] == "criado"
    assert linha["entidade_id"] == resposta.json()["id"]
    assert linha["payload"]["imagem"] == {"mime": "image/png", "tamanho_bytes": len(PNG)}
    assert linha["interpretacao_id"] is None


def test_sku_duplicado_409_com_campo(cliente, usuario):
    resposta = cliente.post(
        "/api/v1/produtos", json=produto_json(sku="SKU-000001"), headers={"X-Usuario": usuario}
    )

    assert resposta.status_code == 409
    assert resposta.json() == {"erros": [{"campo": "sku", "mensagem": "SKU ja cadastrado"}]}
    linha = consultar(cliente, "SELECT resultado, campo_erro FROM ops_cadastros WHERE usuario = :u", u=usuario)
    assert linha == [{"resultado": "conflito", "campo_erro": "sku"}]


def test_cnpj_invalido_422_sem_ecoar_valor(cliente, usuario):
    cnpj = "11.222.333/0001-99"
    resposta = cliente.post(
        "/api/v1/fornecedores",
        json={"nome": "X", "cnpj": cnpj, "cidade": "Campinas", "estado": "SP"},
        headers={"X-Usuario": usuario},
    )

    assert resposta.status_code == 422
    assert resposta.json()["erros"][0]["campo"] == "cnpj"
    assert cnpj not in resposta.text


def test_idempotency_key_repete_resposta_sem_gravar(cliente, usuario, monkeypatch):
    cabecalhos = {"X-Usuario": usuario, "Idempotency-Key": "chave-1"}
    dados = produto_json()
    primeira = cliente.post("/api/v1/produtos", json=dados, headers=cabecalhos)
    assert primeira.status_code == 201

    async def proibido(_dados):
        raise AssertionError("service chamado na repeticao")

    monkeypatch.setattr(produto, "cadastrar", proibido)
    segunda = cliente.post("/api/v1/produtos", json=dados, headers=cabecalhos)

    assert segunda.status_code == 201
    assert segunda.json() == primeira.json()


def test_corpo_acima_do_limite_413(monkeypatch, usuario):
    monkeypatch.setattr(obter_configuracao(), "ops_imagem_max_bytes", 1024)
    with TestClient(criar_app()) as cliente:
        grande = base64.b64encode(PNG + b"\x00" * 200_000).decode()
        resposta = cliente.post(
            "/api/v1/produtos",
            json=produto_json(imagem={"conteudo_base64": grande}),
            headers={"X-Usuario": usuario},
        )
    assert resposta.status_code == 413


def test_erro_inesperado_500_sem_mensagem(cliente, usuario, monkeypatch):
    async def explode(_dados):
        raise RuntimeError("detalhe-interno-secreto")

    monkeypatch.setattr(produto, "cadastrar", explode)
    resposta = cliente.post("/api/v1/produtos", json=produto_json(), headers={"X-Usuario": usuario})

    assert resposta.status_code == 500
    assert resposta.json() == {"erro": "Erro interno"}
    assert "secreto" not in resposta.text
    linha = consultar(cliente, "SELECT resultado FROM ops_cadastros WHERE usuario = :u", u=usuario)
    assert linha == [{"resultado": "erro"}]


# --- apoio ao formulario -----------------------------------------------


def test_rotas_de_apoio(cliente):
    categorias = cliente.get("/api/v1/categorias").json()
    assert any(" > " in c["caminho"] for c in categorias)

    fornecedores = cliente.get("/api/v1/fornecedores", params={"termo": "casa"}).json()
    assert 0 < len(fornecedores) <= obter_configuracao().ops_max_fornecedores_busca
    assert cliente.get("/api/v1/fornecedores", params={"termo": "x"}).status_code == 422

    moda = next(c["id"] for c in categorias if c["caminho"] == "Moda")
    sku = cliente.get("/api/v1/produtos/sku-sugerido", params={"categoria_id": moda}).json()
    assert sku == {"sku": "MOD-000001"}
