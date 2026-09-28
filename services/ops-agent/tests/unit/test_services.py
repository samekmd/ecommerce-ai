"""Services contra o target_db local, sem deixar nada gravado.

sessao_escrita e trocada por uma versao dentro de uma transacao externa
que sempre termina em rollback: o commit do service vira release de
savepoint e o objeto devolvido continua utilizavel, como em producao.
"""

import asyncio
import base64
import uuid
from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ops_agent.config import obter_configuracao
from ops_agent.database import encerrar_engines, sessao_leitura, verificar_conexoes
from ops_agent.database.escrita import obter_engine_escrita
from ops_agent.repositories import produto as produto_repository
from ops_agent.schemas.categoria import CategoriaCadastro
from ops_agent.schemas.cupom import CupomCadastro
from ops_agent.schemas.fornecedor import FornecedorCadastro
from ops_agent.schemas.produto import ProdutoCadastro
from ops_agent.services import categoria, cupom, fornecedor, produto
from ops_agent.services.erros import (
    CONSTRAINTS,
    ErroConflito,
    ErroValidacao,
    traduzir_erro_integridade,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


@asynccontextmanager
async def sessao_sem_commit():
    async with obter_engine_escrita().connect() as conexao:
        externa = await conexao.begin()
        sessao = AsyncSession(
            bind=conexao,
            expire_on_commit=False,
            autoflush=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            async with sessao.begin():
                yield sessao
        finally:
            await sessao.close()
            await externa.rollback()


def rodar(corrotina):
    async def _executar():
        try:
            return await corrotina
        finally:
            await encerrar_engines()

    return asyncio.run(_executar())


@pytest.fixture(scope="module", autouse=True)
def banco_disponivel():
    obter_configuracao.cache_clear()
    try:
        estado = rodar(verificar_conexoes())
    except Exception as erro:
        pytest.skip(f"configuracao ou banco indisponivel: {erro}")
    if not all(estado.values()):
        pytest.skip(f"target_db inacessivel: {estado}")


@pytest.fixture(autouse=True)
def sem_commit(monkeypatch):
    for modulo in (categoria, cupom, fornecedor, produto):
        monkeypatch.setattr(modulo, "sessao_escrita", sessao_sem_commit)


async def _consultar(sql: str):
    async with sessao_leitura() as sessao:
        return (await sessao.execute(text(sql))).scalar()


def produto_cadastro(**campos) -> ProdutoCadastro:
    dados = {
        "nome": "Camisa teste",
        "sku": f"TST-{uuid.uuid4().hex[:8]}",
        "preco": Decimal("100.00"),
        "estoque": 5,
        "categoria_id": 1,
        "fornecedor_id": 1,
        "imagem": {"conteudo_base64": base64.b64encode(PNG).decode()},
    }
    return ProdutoCadastro(**(dados | campos))


# --- funcoes puras ------------------------------------------------------


@pytest.mark.parametrize(
    ("nome", "prefixo"),
    [("Vestuário", "VES"), ("Eletrônicos", "ELE"), ("TV", "SKU"), (None, "SKU"), ("", "SKU")],
)
def test_prefixo_sku(nome, prefixo):
    assert produto.prefixo_sku(nome) == prefixo


def test_constraints_mapeadas_existem_no_banco():
    async def nomes():
        async with sessao_leitura() as sessao:
            linhas = await sessao.execute(text("SELECT conname FROM pg_constraint"))
            return {linha[0] for linha in linhas}

    assert set(CONSTRAINTS) - rodar(nomes()) == set()


# --- produto ------------------------------------------------------------


def test_cadastrar_produto_valido():
    criado = rodar(produto.cadastrar(produto_cadastro()))
    assert criado.id > 0
    assert criado.sku.startswith("TST-")


def test_produto_sku_duplicado():
    with pytest.raises(ErroConflito) as erro:
        rodar(produto.cadastrar(produto_cadastro(sku="SKU-000001")))
    assert erro.value.campo == "sku"


def test_produto_categoria_inexistente():
    with pytest.raises(ErroValidacao) as erro:
        rodar(produto.cadastrar(produto_cadastro(categoria_id=999_999)))
    assert erro.value.campo == "categoria_id"


def test_produto_fornecedor_inativo_ou_inexistente():
    inativo = rodar(_consultar("SELECT id FROM fornecedores WHERE NOT ativo LIMIT 1")) or 999_999
    with pytest.raises(ErroValidacao) as erro:
        rodar(produto.cadastrar(produto_cadastro(fornecedor_id=inativo)))
    assert erro.value.campo == "fornecedor_id"


def test_produto_imagem_acima_do_limite(monkeypatch):
    monkeypatch.setattr(obter_configuracao(), "ops_imagem_max_bytes", len(PNG) - 1)
    # Sem sessao: se o service abrisse uma, o monkeypatch abaixo explodiria.
    monkeypatch.setattr(produto, "sessao_escrita", None)

    with pytest.raises(ErroValidacao) as erro:
        rodar(produto.cadastrar(produto_cadastro()))
    assert erro.value.campo == "imagem"


def test_corrida_de_sku_traduzida_pelo_nome_da_constraint():
    # Pula a checagem do service: o INSERT direto simula outro cadastro
    # gravando o mesmo SKU entre a checagem e o INSERT.
    async def inserir_duplicado():
        async with sessao_sem_commit() as sessao:
            await produto_repository.inserir(sessao, produto_cadastro(sku="SKU-000001"))

    with pytest.raises(IntegrityError) as erro:
        rodar(inserir_duplicado())

    traduzido = traduzir_erro_integridade(erro.value)
    assert isinstance(traduzido, ErroConflito)
    assert traduzido.campo == "sku"


def test_sugerir_sku_usa_prefixo_da_categoria():
    moda = rodar(_consultar("SELECT id FROM categorias WHERE nome = 'Moda'"))
    assert rodar(produto.sugerir_sku(moda)).sku == "MOD-000001"
    assert rodar(produto.sugerir_sku(None)).sku.startswith("SKU-")


# --- categoria, fornecedor, cupom --------------------------------------


def test_categoria_nome_duplicado_ignora_caixa():
    with pytest.raises(ErroConflito) as erro:
        rodar(categoria.cadastrar(CategoriaCadastro(nome="moda")))
    assert erro.value.campo == "nome"


def test_categoria_pai_inexistente():
    dados = CategoriaCadastro(nome=f"teste-{uuid.uuid4()}", categoria_pai_id=999_999)
    with pytest.raises(ErroValidacao) as erro:
        rodar(categoria.cadastrar(dados))
    assert erro.value.campo == "categoria_pai_id"


def test_cadastrar_categoria_valida():
    criada = rodar(categoria.cadastrar(CategoriaCadastro(nome=f"teste-{uuid.uuid4()}")))
    assert criada.id > 0


def test_fornecedor_cnpj_duplicado():
    # CNPJs do seed nao tem digito valido; model_construct pula o schema
    # para exercitar so a regra do service.
    dados = FornecedorCadastro.model_construct(
        nome="Dup", cnpj="00000000000001", email_contato=None, telefone=None,
        cidade="Campinas", estado="SP",
    )
    with pytest.raises(ErroConflito) as erro:
        rodar(fornecedor.cadastrar(dados))
    assert erro.value.campo == "cnpj"


def test_cadastrar_fornecedor_valido():
    dados = FornecedorCadastro(nome="XYZ Ltda", cnpj="11222333000181", cidade="Campinas", estado="SP")
    criado = rodar(fornecedor.cadastrar(dados))
    assert criado.id > 0
    assert criado.ativo is True


def test_buscar_fornecedores_respeita_limite():
    limite = obter_configuracao().ops_max_fornecedores_busca
    assert 0 < len(rodar(fornecedor.buscar("casa"))) <= limite


def test_cupom_codigo_duplicado_ignora_caixa():
    dados = CupomCadastro(
        codigo="cupom0001",
        percentual_desconto=Decimal("10"),
        validade_inicio=date(2026, 9, 1),
        validade_fim=date(2026, 9, 30),
    )
    with pytest.raises(ErroConflito) as erro:
        rodar(cupom.cadastrar(dados))
    assert erro.value.campo == "codigo"
