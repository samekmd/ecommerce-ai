"""Estado do agente: historico de mensagens do loop ReAct."""

from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    # Incrementado por nodo_agente a cada chamada ao LLM. Sem reducer:
    # sobrescrita simples. Cumulativo pela vida da thread inteira (nao
    # resetado por pergunta) - aceitavel enquanto uma thread cobre poucas
    # perguntas; documentar como limitacao conhecida.
    iteracoes: int
