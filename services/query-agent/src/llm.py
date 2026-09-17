"""Factory do LLM (Groq) com as tools do agente ja vinculadas."""

from functools import lru_cache

from langchain_core.runnables import Runnable
from langchain_groq import ChatGroq

from src.config import configuracao
from src.tools.registro import TOOLS


@lru_cache(maxsize=1)
def obter_llm() -> Runnable:
    """Monta o ChatGroq a partir de configuracao com TOOLS ja vinculadas.

    Cacheado (mesmo padrao de config.py::obter_configuracao): uma unica
    instancia de client HTTP por processo, em vez de recriar a cada
    rodada do loop. Groq nao suporta tool-calling strict - nao passar
    esse kwarg. max_tokens e explicito porque contas on-demand da Groq
    tem teto de output tokens por minuto - sem isso, uma unica resposta
    longa pode estourar o limite da conta.
    """
    llm = ChatGroq(
        model=configuracao.groq_model,
        temperature=configuracao.groq_temperature,
        api_key=configuracao.groq_api_key,
        max_tokens=configuracao.groq_max_tokens,
        reasoning_effort='medium'
    )
    return llm.bind_tools(TOOLS)
