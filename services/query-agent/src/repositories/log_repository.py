"""Registro de execucao das tools do agente. Append-only."""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.log import Log
from src.observabilidade import logar_chamada


@logar_chamada
def registrar(
    sessao: Session,
    tool_name: str,
    thread_id: str | None = None,
    pergunta: str | None = None,
    argumentos: dict[str, Any] | None = None,
    query_executada: str | None = None,
    sucesso: bool = True,
    erro: str | None = None,
    linhas_retornadas: int | None = None,
    duracao_ms: int | None = None,
) -> Log:
    log = Log(
        tool_name=tool_name,
        thread_id=thread_id,
        pergunta=pergunta,
        argumentos=argumentos,
        query_executada=query_executada,
        sucesso=sucesso,
        erro=erro,
        linhas_retornadas=linhas_retornadas,
        duracao_ms=duracao_ms,
    )
    sessao.add(log)
    return log


@logar_chamada
def listar_por_thread(sessao: Session, thread_id: str, limite: int = 100) -> Sequence[Log]:
    return sessao.scalars(
        select(Log)
        .where(Log.thread_id == thread_id)
        .order_by(Log.criado_em.desc())
        .limit(limite)
    ).all()


@logar_chamada
def listar_falhas_recentes(sessao: Session, limite: int = 50) -> Sequence[Log]:
    return sessao.scalars(
        select(Log)
        .where(Log.sucesso.is_(False))
        .order_by(Log.criado_em.desc())
        .limit(limite)
    ).all()
