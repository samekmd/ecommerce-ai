"""Decorator e helpers de logging compartilhados.

So para stdout via `logging` padrao. Nao confundir com os outros dois
registros do projeto: a tabela `logs` do app_db (auditoria de negocio,
gravada por log_service/log_repository) e o tracing no Langfuse (em
src/observability/).
"""

import functools
import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def logar_chamada(func: F) -> F:
    """Loga nome, duracao e desfecho de uma funcao de repositories/.

    Sucesso em DEBUG (silencioso por padrao). Excecao em WARNING - uma
    falha vinda do banco nessa camada e minimamente relevante mesmo sem
    rebaixar o nivel de log. Nao loga argumentos: funcoes como
    coluna_repository.criar_lote recebem listas grandes de dict e
    execucao_sql_service.executar recebe SQL potencialmente longo -
    manter o decorator cego a argumentos evita ter que resolver politica
    de truncamento por tipo numa funcao generica.
    """
    logger = logging.getLogger(func.__module__)

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        inicio = time.perf_counter()
        try:
            resultado = func(*args, **kwargs)
        except Exception as excecao:
            duracao_ms = (time.perf_counter() - inicio) * 1000
            logger.warning(
                "%s falhou apos %.1fms: %s: %s",
                func.__qualname__, duracao_ms, type(excecao).__name__, excecao,
            )
            raise
        duracao_ms = (time.perf_counter() - inicio) * 1000
        logger.debug("%s concluida em %.1fms", func.__qualname__, duracao_ms)
        return resultado

    return wrapper  # type: ignore[return-value]


def truncar_texto(texto: str, max_chars: int = 200) -> str:
    """Corta uma string longa para uso em mensagem de log (ex.: SQL)."""
    if len(texto) <= max_chars:
        return texto
    return f"{texto[:max_chars]}... ({len(texto)} chars)"


def resumir_lista(itens: list[Any], max_itens: int = 20) -> str:
    """Representa uma lista em log sem estourar a linha (ex.: tabela_ids)."""
    if len(itens) <= max_itens:
        return str(itens)
    return f"{itens[:max_itens]}... ({len(itens)} itens no total)"
