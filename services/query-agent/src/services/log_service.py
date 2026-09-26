"""Medicao de duracao + registro de log, compartilhado pelas services.

Cada service ajusta os campos de ContextoLog conforme resolve o
resultado; o log e gravado no finally, sucesso ou falha - inclusive se
uma excecao nao mapeada escapar do bloco.
"""

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from src.repositories import log_repository

logger = logging.getLogger(__name__)


@dataclass
class ContextoLog:
    query_executada: str | None = None
    sucesso: bool = True
    erro: str | None = None
    linhas_retornadas: int | None = None
    duracao_ms_override: int | None = None  # so execucao_sql_service usa


@contextmanager
def medir_e_registrar(
    sessao: Session,
    tool_name: str,
    thread_id: str | None = None,
    pergunta: str | None = None,
    argumentos: dict[str, Any] | None = None,
) -> Iterator[ContextoLog]:
    ctx = ContextoLog()
    inicio = time.perf_counter()
    try:
        yield ctx
    except Exception as excecao:
        ctx.sucesso = False
        ctx.erro = str(excecao)
        raise
    finally:
        duracao_ms = ctx.duracao_ms_override
        if duracao_ms is None:
            duracao_ms = int((time.perf_counter() - inicio) * 1000)
        try:
            log_repository.registrar(
                sessao,
                tool_name=tool_name,
                thread_id=thread_id,
                pergunta=pergunta,
                argumentos=argumentos,
                query_executada=ctx.query_executada,
                sucesso=ctx.sucesso,
                erro=ctx.erro,
                linhas_retornadas=ctx.linhas_retornadas,
                duracao_ms=duracao_ms,
            )
        except Exception:
            # Uma nova excecao levantada aqui dentro do finally substitui
            # silenciosamente qualquer excecao original que estivesse
            # propagando do bloco try - por isso ERROR (nao DEBUG) e
            # inclui ctx.erro na mensagem, para nao perder de vista qual
            # era o erro original potencialmente mascarado.
            logger.exception(
                "Falha ao gravar log de auditoria (tool=%s, thread=%s, erro_original=%s) - "
                "pode estar mascarando essa excecao original",
                tool_name, thread_id, ctx.erro,
            )
            raise
