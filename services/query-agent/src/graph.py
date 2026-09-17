"""Grafo do agente Text-to-SQL: no do agente + ToolNode + roteamento."""

from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

from src.config import configuracao
from src.database.database import sessao_app
from src.llm import obter_llm
from src.repositories import prompt_repository
from src.routing import rotear
from src.state import State
from src.tools.registro import TOOLS

CHAVE_PROMPT_SISTEMA = "agente_sql_sistema"


class PromptNaoConfigurado(RuntimeError):
    """Nenhuma versao ativa para CHAVE_PROMPT_SISTEMA no banco da app.

    Erro de ambiente (seed nao rodado, ou prompt desativado por
    engano), nao algo que o LLM cause ou possa corrigir - propaga como
    excecao, mesmo espirito de ContextoInvalido em src/tools/contexto.py.
    """


def nodo_agente(state: State, config: RunnableConfig) -> dict:
    """Chama o LLM com o prompt de sistema ativo e o historico atual.

    Abre e fecha a sessao do banco da app so para buscar o prompt
    (regra 6 do CLAUDE.md: nunca fica aberta durante a chamada ao LLM,
    que pode levar segundos). state.get() em vez de state["iteracoes"]:
    tolera a ausencia do campo na primeira chamada de uma thread nova,
    sem depender de quem monta o input inicial lembrar de inicializa-lo.
    """
    with sessao_app() as sessao:
        prompt = prompt_repository.buscar_ativo(sessao, CHAVE_PROMPT_SISTEMA)
    if prompt is None:
        raise PromptNaoConfigurado(
            f"Nenhum prompt ativo para a chave {CHAVE_PROMPT_SISTEMA!r}. "
            "Rode scripts/seed_prompt.py antes de usar o grafo."
        )

    mensagens = [SystemMessage(prompt.conteudo), *state["messages"]]
    resposta = obter_llm().invoke(mensagens, config)
    nova_iteracao = state.get("iteracoes", 0) + 1

    if nova_iteracao >= configuracao.max_iteracoes and resposta.tool_calls:
        # Substitui a resposta por uma sem tool_calls pendentes: evita
        # deixar uma AIMessage pedindo uma tool que nunca vai rodar como
        # ultima mensagem do grafo (rotear ja cortaria por iteracoes,
        # mas a mensagem ficaria confusa para quem le a transcricao).
        aviso = (
            f"\n\n[Limite de {configuracao.max_iteracoes} iteracoes atingido "
            "antes de concluir a consulta; a resposta acima pode estar incompleta.]"
        )
        resposta = AIMessage(content=(resposta.content or "") + aviso)

    return {"messages": [resposta], "iteracoes": nova_iteracao}


def construir_grafo() -> CompiledStateGraph:
    """Monta e compila o grafo do agente Text-to-SQL.

    Funcao (nao so um singleton de modulo) para permitir compilar
    variantes em teste - outro checkpointer, ou obter_llm() com
    monkeypatch aplicado antes de chamar esta funcao.
    """
    builder = StateGraph(State)
    builder.add_node("agente", nodo_agente)
    builder.add_node("tools", ToolNode(TOOLS))
    builder.add_edge(START, "agente")
    builder.add_conditional_edges("agente", rotear, {"tools": "tools", END: END})
    builder.add_edge("tools", "agente")
    return builder.compile(checkpointer=InMemorySaver())


grafo = construir_grafo()
