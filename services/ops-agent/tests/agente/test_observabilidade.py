"""Tracing do agente com um Langfuse real e exporter em memoria: nada sai da maquina."""

import json
import uuid

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel

from ops_agent.agente.agente import agente
from ops_agent.agente.prompts.sistema import PROMPT_EMBUTIDO, PromptSistema
from ops_agent.config import obter_configuracao
from ops_agent.observabilidade import tracing
from tests.conftest import rodar


@pytest.fixture
def exportador(monkeypatch):
    from langfuse import Langfuse

    exportador = InMemorySpanExporter()
    cliente = Langfuse(
        # Chave unica: o SDK guarda um cliente por public_key no processo.
        public_key=f"pk-lf-teste-{uuid.uuid4().hex}",
        secret_key="sk-lf-teste",
        base_url="http://127.0.0.1:9",
        span_exporter=exportador,
        should_export_span=lambda span: True,
    )
    monkeypatch.setattr(tracing, "obter_cliente", lambda: cliente)
    Agent.instrument_all()
    yield exportador, cliente
    Agent.instrument_all(False)
    cliente.shutdown()


def modelo_com_tool():
    def modelo(mensagens, info):
        if not any(isinstance(p, ToolReturnPart) for m in mensagens for p in m.parts):
            return ModelResponse(parts=[ToolCallPart("verificar_codigo_cupom", {"codigo": "BLACK 10"})])
        return ModelResponse(
            parts=[ToolCallPart("pedir_esclarecimento", {"motivo": "ambiguo", "mensagem": "?"})]
        )

    return FunctionModel(modelo)


def atributos(span) -> str:
    return json.dumps({k: str(v) for k, v in (span.attributes or {}).items()})


def test_trace_une_raiz_agente_modelo_e_tool(exportador, deps):
    exportador, cliente = exportador
    deps.abrir_sessao = None  # codigo com formato invalido nao abre sessao

    async def cenario():
        async with tracing.rastrear_interpretacao("maria", "cupom BLACK 10", PROMPT_EMBUTIDO) as rastro:
            resultado = await agente.run("cupom BLACK 10", deps=deps, model=modelo_com_tool())
            rastro.registrar_saida(resultado.output)
            return rastro.trace_id

    trace_id = rodar(cenario())
    cliente.flush()
    spans = exportador.get_finished_spans()

    assert trace_id
    nomes = [s.name for s in spans]
    assert "interpretar" in nomes
    assert any("verificar_codigo_cupom" in n for n in nomes)
    assert len({format(s.context.trace_id, "032x") for s in spans}) == 1
    assert format(spans[0].context.trace_id, "032x") == trace_id

    raiz = next(s for s in spans if s.name == "interpretar")
    texto = atributos(raiz)
    assert "maria" in texto
    assert "ops-agent" in texto
    assert "ops-interpretar" in texto

    chave = obter_configuracao().openrouter_api_key.get_secret_value()
    assert all(chave not in atributos(s) for s in spans)


def test_prompt_do_langfuse_ligado_a_generation(exportador, deps):
    exportador, cliente = exportador
    from langfuse.api.prompts.types.prompt import Prompt_Text
    from langfuse.model import TextPromptClient

    prompt_langfuse = TextPromptClient(
        Prompt_Text(
            name="ops_agente_sistema", version=7, prompt="PROMPT V7", config={}, labels=["production"],
            tags=[],
        )
    )
    prompt = PromptSistema(texto="PROMPT V7", versao=7, cliente=prompt_langfuse)
    deps.prompt_sistema = prompt.texto

    def modelo(mensagens, info):
        return ModelResponse(
            parts=[ToolCallPart("pedir_esclarecimento", {"motivo": "ambiguo", "mensagem": "?"})]
        )

    async def cenario():
        async with tracing.rastrear_interpretacao("joao", "oi", prompt):
            await agente.run("oi", deps=deps, model=FunctionModel(modelo))

    rodar(cenario())
    cliente.flush()
    spans = exportador.get_finished_spans()

    ligados = [s for s in spans if "ops_agente_sistema" in atributos(s)]
    assert ligados, [atributos(s) for s in spans]
    assert any("7" in atributos(s) for s in ligados)


def test_sem_cliente_rastro_nulo(monkeypatch):
    monkeypatch.setattr(tracing, "obter_cliente", lambda: None)

    async def cenario():
        async with tracing.rastrear_interpretacao("u", "m", PROMPT_EMBUTIDO) as rastro:
            rastro.registrar_erro("x")
            return rastro.trace_id

    assert rodar(cenario()) is None


def test_falha_ao_abrir_trace_nao_derruba(monkeypatch):
    class Quebrado:
        def start_as_current_observation(self, **kwargs):
            raise RuntimeError("langfuse quebrado")

    monkeypatch.setattr(tracing, "obter_cliente", lambda: Quebrado())

    async def cenario():
        async with tracing.rastrear_interpretacao("u", "m", PROMPT_EMBUTIDO) as rastro:
            return rastro.trace_id, "seguiu"

    assert rodar(cenario()) == (None, "seguiu")


def test_erro_da_aplicacao_atravessa(exportador):
    class ErroDaAplicacao(Exception):
        pass

    async def cenario():
        async with tracing.rastrear_interpretacao("u", "m", PROMPT_EMBUTIDO):
            raise ErroDaAplicacao

    with pytest.raises(ErroDaAplicacao):
        rodar(cenario())


def test_prompt_de_sistema_vem_das_deps(deps):
    visto = {}
    deps.prompt_sistema = "PROMPT X"

    def modelo(mensagens, info):
        visto["instrucoes"] = info.instructions
        return ModelResponse(
            parts=[ToolCallPart("pedir_esclarecimento", {"motivo": "ambiguo", "mensagem": "?"})]
        )

    rodar(agente.run("oi", deps=deps, model=FunctionModel(modelo)))

    assert visto["instrucoes"].startswith("PROMPT X")
    assert "28/09/2026" in visto["instrucoes"]
