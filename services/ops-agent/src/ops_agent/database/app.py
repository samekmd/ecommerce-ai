"""Engine e sessao do app_db, onde fica a auditoria do agente."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from ops_agent.config import obter_configuracao
from ops_agent.database.engine import criar_engine


@lru_cache(maxsize=1)
def obter_engine_app() -> AsyncEngine:
    return criar_engine(obter_configuracao().app_database_url, "app")


@lru_cache(maxsize=1)
def _fabrica_de_sessoes_app() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(obter_engine_app(), expire_on_commit=False, autoflush=False)


@asynccontextmanager
async def sessao_app() -> AsyncIterator[AsyncSession]:
    """Uma transacao de auditoria: commit ao sair, rollback em erro.

    Independente da transacao do cadastro, que e em outro banco: nao ha
    atomicidade entre os dois.
    """
    async with _fabrica_de_sessoes_app()() as sessao, sessao.begin():
        yield sessao
