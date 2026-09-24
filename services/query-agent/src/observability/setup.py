"""Cliente Langfuse e callback handler do processo.

Tracing distribuido das perguntas do agente. Nao confundir com
src/log_stdout.py (log de stdout) nem com a tabela `logs` do app_db
(auditoria de negocio).
"""

import logging
from functools import lru_cache

from langfuse import Langfuse
from langfuse.langchain import CallbackHandler

from src.config import configuracao

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def obter_cliente() -> Langfuse | None:
    """Cliente unico do processo, ou None quando nao ha credenciais.

    Construtor explicito em vez de get_client(): o get_client le
    LANGFUSE_* direto do ambiente, o que depende de o .env ja ter sido
    carregado neste ponto e nao oferece como desligar o tracing.
    """
    if not configuracao.langfuse_configurado:
        logger.warning("Langfuse sem credenciais configuradas - tracing desligado.")
        return None

    return Langfuse(
        public_key=configuracao.langfuse_public_key,
        secret_key=configuracao.langfuse_secret_key,
        base_url=configuracao.langfuse_base_url,
        environment=configuracao.ambiente,
        tracing_enabled=configuracao.langfuse_tracing_enabled,
    )


@lru_cache(maxsize=1)
def obter_handler() -> CallbackHandler | None:
    """Handler para passar em `callbacks` do config do grafo.

    Chama obter_cliente() antes de proposito: o CallbackHandler resolve
    o cliente ja registrado para aquela public_key, entao o cliente
    precisa existir primeiro.
    """
    if obter_cliente() is None:
        return None
    return CallbackHandler(public_key=configuracao.langfuse_public_key)
