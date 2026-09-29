"""As tools registradas num Agent real, com FunctionModel (sem rede)."""

import json

import pytest
from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from ops_agent.agente.deps import DependenciasAgente
from ops_agent.agente.tools import TOOLS
from tests.conftest import rodar

pytestmark = pytest.mark.usefixtures("banco_disponivel")


def test_tools_expostas_ao_modelo_e_resultado_chega_ao_llm(deps):
    vistos: dict = {}

    def modelo(mensagens, info: AgentInfo) -> ModelResponse:
        vistos["tools"] = {tool.name: tool for tool in info.function_tools}
        retornos = [
            parte
            for mensagem in mensagens
            for parte in mensagem.parts
            if isinstance(parte, ToolReturnPart)
        ]
        if not retornos:
            return ModelResponse(parts=[ToolCallPart("buscar_fornecedores", {"termo": "casa"})])
        vistos["retorno"] = retornos[0]
        return ModelResponse(parts=[TextPart("ok")])

    agente = Agent(FunctionModel(modelo), deps_type=DependenciasAgente, tools=TOOLS)
    resultado = rodar(agente.run("fornecedor Casa", deps=deps))

    assert resultado.output == "ok"
    assert set(vistos["tools"]) == {
        "listar_categorias",
        "buscar_fornecedores",
        "verificar_codigo_cupom",
    }

    busca = vistos["tools"]["buscar_fornecedores"]
    assert "ATIVOS" in busca.description
    assert busca.parameters_json_schema["properties"]["termo"]["description"]
    assert vistos["tools"]["listar_categorias"].parameters_json_schema["properties"] == {}

    conteudo = vistos["retorno"].model_response_str()
    fornecedores = json.loads(conteudo)
    assert fornecedores and {"id", "nome"} <= set(fornecedores[0])
    assert deps.fornecedores_vistos == {f["id"] for f in fornecedores}
