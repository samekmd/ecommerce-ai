"""Extracao do contexto injetado pelo LangGraph nas tools.

Nao chamado por services - so pelos arquivos de *_tool.py.
"""

import logging

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

logger = logging.getLogger(__name__)


class ContextoInvalido(RuntimeError):
    """banco_id ausente ou mal formado no RunnableConfig.

    Erro de wiring de quem monta o config ao invocar o grafo, nunca algo
    que o LLM escolheu e possa corrigir reescrevendo argumentos - por
    isso propaga como excecao, no mesmo espirito de ConfiguracaoInvalida
    em src/config.py, em vez de virar texto de erro para o LLM.
    """


def extrair_banco_id(config: RunnableConfig) -> int:
    configuravel = config.get("configurable", {}) if config else {}
    banco_id = configuravel.get("banco_id")
    if not isinstance(banco_id, int):
        logger.error(
            "config['configurable']['banco_id'] ausente ou invalido: %r", banco_id
        )
        raise ContextoInvalido(
            "config['configurable']['banco_id'] ausente ou invalido - "
            "verifique como o grafo foi invocado."
        )
    return banco_id


def extrair_thread_id(config: RunnableConfig) -> str | None:
    configuravel = config.get("configurable", {}) if config else {}
    return configuravel.get("thread_id")


def extrair_pergunta(state: dict) -> str | None:
    # So usado para compor o log nos services, nunca influencia a
    # logica de negocio da tool.
    for mensagem in reversed(state.get("messages", [])):
        if isinstance(mensagem, HumanMessage):
            conteudo = mensagem.content
            return conteudo if isinstance(conteudo, str) else str(conteudo)
    return None
