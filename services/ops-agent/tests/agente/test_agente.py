"""Agente com FunctionModel: fluxo de tools, validador de saida e limites. Sem rede."""

from datetime import date

import pytest
from pydantic_ai import ModelRetry
from pydantic_ai.exceptions import UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_ai.messages import ModelResponse, RetryPromptPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.usage import UsageLimits

from ops_agent.agente import agente as modulo_agente
from ops_agent.agente.agente import _checar_id, agente
from ops_agent.schemas.cupom import CupomProposta
from ops_agent.schemas.interpretacao import PedidoEsclarecimento
from ops_agent.schemas.produto import ProdutoProposta
from tests.conftest import rodar


def partes(mensagens, tipo):
    return [p for m in mensagens for p in m.parts if isinstance(p, tipo)]


def chamar(tool: str, **args) -> ModelResponse:
    return ModelResponse(parts=[ToolCallPart(tool, args)])


def executar(modelo, deps, **kwargs):
    return rodar(agente.run("frase", deps=deps, model=FunctionModel(modelo), **kwargs))


# --- contrato com o modelo ---------------------------------------------


def test_modelo_recebe_output_tools_e_data_de_hoje(deps):
    visto: dict = {}

    def modelo(mensagens, info: AgentInfo):
        visto["info"] = info
        return chamar("pedir_esclarecimento", motivo="ambiguo", mensagem="O que cadastrar?")

    executar(modelo, deps)

    info = visto["info"]
    assert {t.name for t in info.output_tools} == {
        "propor_produto",
        "propor_fornecedor",
        "propor_categoria",
        "propor_cupom",
        "pedir_esclarecimento",
    }
    assert info.allow_text_output is False
    assert "segunda-feira, 28/09/2026" in info.instructions
    assert "Nunca invente" in info.instructions


# --- validador: IDs ----------------------------------------------------


def test_id_alucinado_gera_retry_e_modelo_corrige(deps):
    visto: dict = {}

    def modelo(mensagens, info):
        retries = partes(mensagens, RetryPromptPart)
        if not retries:
            return chamar("propor_produto", nome="Camisa", categoria_id=999_999)
        visto["retry"] = retries[0].model_response()
        return chamar("propor_produto", nome="Camisa", categoria_id=None, avisos=["Sem categoria"])

    resultado = executar(modelo, deps)

    assert isinstance(resultado.output, ProdutoProposta)
    assert resultado.output.categoria_id is None
    assert "listar_categorias" in visto["retry"]


@pytest.mark.usefixtures("banco_disponivel")
def test_id_devolvido_por_tool_e_aceito(deps):
    def modelo(mensagens, info):
        retornos = partes(mensagens, ToolReturnPart)
        if not retornos:
            return chamar("listar_categorias")
        categoria_id = retornos[0].content[0].id
        return chamar("propor_produto", nome="Camisa", preco=100, estoque=5, categoria_id=categoria_id)

    resultado = executar(modelo, deps)

    assert resultado.output.categoria_id in deps.categorias_vistas
    assert resultado.output.estoque == 5


def test_retries_esgotados(deps):
    def modelo(mensagens, info):
        return chamar("propor_produto", nome="Camisa", fornecedor_id=999_999)

    with pytest.raises(UnexpectedModelBehavior):
        executar(modelo, deps, retries=2)


def test_categoria_pai_validada(deps):
    deps.categorias_vistas.update({1, 2})

    def modelo(mensagens, info):
        if partes(mensagens, RetryPromptPart):
            return chamar("propor_categoria", nome="Camisetas", categoria_pai_id=2)
        return chamar("propor_categoria", nome="Camisetas", categoria_pai_id=7)

    assert executar(modelo, deps).output.categoria_pai_id == 2


def test_checar_id_mensagens():
    _checar_id(None, set(), "categoria_id", "listar_categorias")
    _checar_id(3, {3}, "categoria_id", "listar_categorias")

    with pytest.raises(ModelRetry, match="Chame buscar_fornecedores primeiro"):
        _checar_id(9, set(), "fornecedor_id", "buscar_fornecedores")
    with pytest.raises(ModelRetry, match="IDs validos: 2, 10, 30"):
        _checar_id(9, {30, 2, 10}, "categoria_id", "listar_categorias")


# --- validador: cupom --------------------------------------------------


def test_cupom_sem_inicio_recebe_hoje_e_codigo_normalizado(deps):
    def modelo(mensagens, info):
        return chamar(
            "propor_cupom", codigo=" black10 ", percentual_desconto=10, validade_fim="2026-09-30"
        )

    saida = executar(modelo, deps).output

    assert isinstance(saida, CupomProposta)
    assert saida.validade_inicio == deps.hoje
    assert saida.codigo == "BLACK10"


def test_cupom_com_fim_antes_do_inicio_gera_retry(deps):
    visto: dict = {}

    def modelo(mensagens, info):
        retries = partes(mensagens, RetryPromptPart)
        if retries:
            visto["retry"] = retries[0].model_response()
            return chamar("propor_cupom", codigo="X10", percentual_desconto=10, validade_fim="2026-10-31")
        return chamar("propor_cupom", codigo="X10", percentual_desconto=10, validade_fim="2026-09-01")

    assert executar(modelo, deps).output.validade_fim == date(2026, 10, 31)
    assert "validade_fim" in visto["retry"]


def test_esclarecimento_passa_direto(deps):
    def modelo(mensagens, info):
        return chamar(
            "pedir_esclarecimento", motivo="nao_suportado", mensagem="So desconto percentual."
        )

    saida = executar(modelo, deps).output
    assert isinstance(saida, PedidoEsclarecimento)
    assert saida.motivo == "nao_suportado"


# --- limites -----------------------------------------------------------


def test_limite_de_requisicoes(deps):
    deps.abrir_sessao = None  # termo curto recusa antes de abrir sessao

    def modelo(mensagens, info):
        return chamar("buscar_fornecedores", termo="x")  # termo curto: retry infinito

    with pytest.raises(UsageLimitExceeded, match="request_limit"):
        executar(modelo, deps, usage_limits=UsageLimits(request_limit=2), retries=10)


# --- interpretar() -----------------------------------------------------


def test_interpretar_usa_config_e_devolve_saida(monkeypatch):
    def modelo(mensagens, info):
        return chamar("propor_produto", nome="Camisa Nike", preco=100, avisos=["Informe o fornecedor"])

    monkeypatch.setattr(modulo_agente, "obter_modelo", lambda: FunctionModel(modelo))

    saida = rodar(modulo_agente.interpretar("Cadastre camisas Nike a 100 reais", "teste"))

    assert isinstance(saida, ProdutoProposta)
    assert saida.nome == "Camisa Nike"
    assert saida.avisos == ["Informe o fornecedor"]
