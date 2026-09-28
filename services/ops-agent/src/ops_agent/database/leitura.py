"""Engine e sessao de leitura, usadas pelas tools do agente (agente_leitura)."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from ops_agent.config import obter_configuracao
from ops_agent.database.engine import criar_engine

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def obter_engine_leitura() -> AsyncEngine:
    """Criada no primeiro uso: importar o modulo nao exige configuracao."""
    return criar_engine(obter_configuracao().ops_leitura_database_url, "leitura")


@asynccontextmanager
async def sessao_leitura() -> AsyncIterator[AsyncSession]:
    """Sessao somente leitura para UMA tool call.

    Nunca envolva o agent.run inteiro: entre duas tool calls ha uma
    chamada ao LLM que pode levar segundos, e a transacao aberta nesse
    intervalo esbarra no idle_in_transaction_session_timeout.

    O role agente_leitura ja bloqueia escrita no banco; a transacao
    READ ONLY e uma segunda camada, barata, para o caso de o role estar
    mal configurado. Termina sempre em rollback: nao ha nada a persistir.

    Uso:
        async with sessao_leitura() as sessao:
            categorias = await categoria_repository.listar(sessao)
    """
    # A conexao sai do pool ja na entrada: pool esgotado ou banco fora do
    # ar estoura aqui, nao no meio de um repository.
    conexao = await obter_engine_leitura().connect()
    try:
        await conexao.execution_options(postgresql_readonly=True)
        async with AsyncSession(bind=conexao, expire_on_commit=False, autoflush=False) as sessao:
            yield sessao
    finally:
        # Numa conexao morta o rollback levanta; sem estes try o close nao
        # roda e a excecao de limpeza substitui o desfecho real do bloco
        # (medido no query-agent).
        try:
            await conexao.rollback()
        except Exception as erro:
            logger.warning("Rollback de leitura falhou: %s", erro)
        try:
            await conexao.close()
        except Exception as erro:
            logger.warning("Close de leitura falhou: %s", erro)
