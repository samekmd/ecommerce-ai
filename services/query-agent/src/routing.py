"""Roteamento do loop ReAct: continuar chamando tools ou finalizar."""

from typing import Literal

from langchain_core.messages import AIMessage

from src.config import configuracao
from src.state import State


def rotear(state: State) -> Literal["tools", "__end__"]:
    """Decide o proximo no apos o agente: tools ou fim do grafo.

    Vai para tools quando a ultima mensagem e uma AIMessage com
    tool_calls pendentes E o teto de configuracao.max_iteracoes ainda
    nao foi atingido. Erro de SQL (ToolMessage de texto) nao e parada
    especial aqui - o loop volta ao agente normalmente para
    autocorrecao (regra 5 do CLAUDE.md); so tool_calls e o numero de
    iteracoes importam para este roteamento.
    """
    ultima = state["messages"][-1]
    tem_tool_calls = isinstance(ultima, AIMessage) and bool(ultima.tool_calls)

    if not tem_tool_calls:
        return "__end__"
    if state["iteracoes"] >= configuracao.max_iteracoes:
        return "__end__"
    return "tools"
