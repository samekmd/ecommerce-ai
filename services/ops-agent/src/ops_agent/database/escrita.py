"""Engine e sessao de escrita, usadas pelos services de cadastro (agente_escrita)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from ops_agent.config import obter_configuracao
from ops_agent.database.engine import criar_engine


@lru_cache(maxsize=1)
def obter_engine_escrita() -> AsyncEngine:
    """Criada no primeiro uso: importar o modulo nao exige configuracao."""
    return criar_engine(obter_configuracao().ops_escrita_database_url, "escrita")


@lru_cache(maxsize=1)
def _fabrica_de_sessoes() -> async_sessionmaker[AsyncSession]:
    # expire_on_commit=False: o service monta o XCriado a partir do objeto
    # depois do commit; expirado, cada atributo dispararia um SELECT (e em
    # async, um erro de lazy load).
    return async_sessionmaker(obter_engine_escrita(), expire_on_commit=False, autoflush=False)


@asynccontextmanager
async def sessao_escrita() -> AsyncIterator[AsyncSession]:
    """Uma transacao de cadastro: commit ao sair do bloco, rollback em erro.

    Aberta pelo service, uma vez por cadastro, e so depois de toda a
    validacao que nao precisa de banco. Produto e imagem vao na mesma
    sessao, portanto na mesma transacao.

    Uso:
        async with sessao_escrita() as sessao:
            produto = await produto_repository.inserir(sessao, dados)
    """
    async with _fabrica_de_sessoes()() as sessao, sessao.begin():
        yield sessao
