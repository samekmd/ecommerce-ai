"""Estado do agente: historico de mensagens do loop ReAct."""

from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    # Incrementado por nodo_agente a cada chamada ao LLM e reiniciado a
    # cada pergunta nova. Sem reducer: sobrescrita simples. Ja foi
    # cumulativo pela thread inteira, e isso fazia a 4a pergunta de uma
    # conversa nascer sem orcamento - os tool_calls eram descartados
    # antes de executar, e a interface mostrava uma query processando
    # para sempre.
    iteracoes: int
