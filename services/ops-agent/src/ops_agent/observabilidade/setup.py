"""Cliente Langfuse do processo e instrumentacao do Pydantic AI."""

import logging
from functools import lru_cache

from langfuse import Langfuse
from pydantic_ai import Agent

from ops_agent.config import obter_configuracao

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def obter_cliente() -> Langfuse | None:
    """Cliente unico do processo, ou None quando nao ha credenciais.

    Construtor explicito em vez de get_client(), como no query-agent: o
    get_client le LANGFUSE_* direto do ambiente, e config.py e o unico
    leitor de ambiente deste servico.
    """
    configuracao = obter_configuracao()
    if not configuracao.langfuse_configurado:
        logger.warning("Langfuse sem credenciais configuradas - tracing desligado.")
        return None

    return Langfuse(
        public_key=configuracao.langfuse_public_key,
        secret_key=configuracao.langfuse_secret_key.get_secret_value(),
        base_url=configuracao.langfuse_base_url,
        environment=configuracao.ambiente,
        tracing_enabled=configuracao.langfuse_tracing_enabled,
    )


def instrumentar_agente() -> bool:
    """Liga os spans OTel do Pydantic AI (run, chamada ao LLM, tools).

    O cliente Langfuse registra o exporter OTel; o filtro padrao do SDK
    exporta os spans gen_ai.* que o Pydantic AI emite. Sem cliente, nada e
    instrumentado e o agente roda sem custo de tracing.
    """
    if obter_cliente() is None:
        return False
    Agent.instrument_all()
    return True


def encerrar() -> None:
    """Flush dos spans pendentes no shutdown; nunca levanta."""
    cliente = obter_cliente()
    if cliente is None:
        return
    try:
        cliente.shutdown()
    except Exception:
        logger.exception("Falha ao encerrar o Langfuse; spans pendentes podem ter se perdido.")
