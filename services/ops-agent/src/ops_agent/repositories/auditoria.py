"""Queries da auditoria no app_db."""

import uuid
from typing import Any

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from ops_agent.models.auditoria import Cadastro, Interpretacao


async def inserir_interpretacao(sessao: AsyncSession, **campos: Any) -> uuid.UUID:
    interpretacao = Interpretacao(**campos)
    sessao.add(interpretacao)
    await sessao.flush()
    return interpretacao.id


async def interpretacao_existe(sessao: AsyncSession, interpretacao_id: uuid.UUID) -> bool:
    consulta = exists().where(Interpretacao.id == interpretacao_id)
    return bool(await sessao.scalar(select(consulta)))


async def inserir_cadastro(sessao: AsyncSession, **campos: Any) -> None:
    sessao.add(Cadastro(**campos))
    await sessao.flush()


async def buscar_resposta_idempotente(
    sessao: AsyncSession, usuario: str, chave: str
) -> dict[str, Any] | None:
    """Resposta de um cadastro ja criado com a mesma chave pelo mesmo usuario."""
    return await sessao.scalar(
        select(Cadastro.resposta).where(
            Cadastro.usuario == usuario,
            Cadastro.chave_idempotencia == chave,
            Cadastro.resultado == "criado",
        )
    )
