"""Factory do LLM (OpenRouter, via init_chat_model) com as tools do agente ja vinculadas."""

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturoExpirou
from functools import lru_cache
from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.messages import AnyMessage
from langchain_core.runnables import Runnable, RunnableConfig

from src.config import configuracao
from src.tools.registro import TOOLS

# Pool dedicado as chamadas ao LLM. O parametro timeout do ChatOpenRouter
# nao e respeitado pela chamada HTTP real nesta versao do SDK (verificado
# com timeout=1ms + max_retries=0 - mesmo assim travou por minutos). O
# unico jeito confiavel de garantir um teto de tempo e rodar a chamada
# numa thread separada e desistir de espera-la no nosso lado; a thread
# presa fica vazando ate a chamada (se algum dia) retornar ou o processo
# reiniciar. Aceitavel numa ferramenta de teste - o tamanho default do
# pool (ate ~32 threads) da folga antes de esgotar.
_executor = ThreadPoolExecutor()


class LLMTimeoutError(RuntimeError):
    """A chamada ao LLM nao respondeu dentro do teto configurado."""


@lru_cache(maxsize=1)
def obter_llm() -> Runnable:
    """Monta o LLM via init_chat_model (OpenRouter) com TOOLS ja vinculadas.

    Cacheado (mesmo padrao de config.py::obter_configuracao): uma unica
    instancia de client HTTP por processo. Migrado de Groq para
    OpenRouter por problemas de formatacao de tool calls nos modelos
    usados via Groq - a config antiga (groq_*) fica dormant em
    Configuracao, sem uso aqui, caso seja necessario reverter.
    """
    llm = init_chat_model(
        configuracao.openrouter_model,
        model_provider="openrouter",
        temperature=configuracao.openrouter_temperature,
        api_key=configuracao.openrouter_api_key,
        max_tokens=configuracao.openrouter_max_tokens,
    )
    return llm.bind_tools(TOOLS)


def invocar_com_timeout(mensagens: list[AnyMessage], config: RunnableConfig) -> Any:
    """Chama obter_llm().invoke(mensagens, config) com um teto de tempo real.

    Ver comentario de _executor: o kwarg timeout do ChatOpenRouter nao
    protege de verdade, entao o teto e imposto aqui, de fora, rodando a
    chamada numa thread e desistindo dela apos
    configuracao.openrouter_timeout_segundos.
    """
    futuro = _executor.submit(obter_llm().invoke, mensagens, config)
    try:
        return futuro.result(timeout=configuracao.openrouter_timeout_segundos)
    except FuturoExpirou:
        raise LLMTimeoutError(
            f"LLM nao respondeu em {configuracao.openrouter_timeout_segundos}s."
        ) from None
