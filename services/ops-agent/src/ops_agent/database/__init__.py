"""Conexao e sessao com o banco de negocio. Nenhuma query mora aqui."""

import logging

from sqlalchemy import text

from ops_agent.database.escrita import _fabrica_de_sessoes, obter_engine_escrita, sessao_escrita
from ops_agent.database.leitura import obter_engine_leitura, sessao_leitura

__all__ = ["encerrar_engines", "sessao_escrita", "sessao_leitura", "verificar_conexoes"]

logger = logging.getLogger(__name__)

_ENGINES = {"leitura": obter_engine_leitura, "escrita": obter_engine_escrita}


async def verificar_conexoes() -> dict[str, bool]:
    """SELECT 1 em cada engine, para o /ready."""
    estado: dict[str, bool] = {}
    for nome, obter in _ENGINES.items():
        try:
            async with obter().connect() as conexao:
                await conexao.execute(text("SELECT 1"))
            estado[nome] = True
        except Exception as erro:
            logger.warning("Banco de %s inacessivel: %s", nome, erro)
            estado[nome] = False
    return estado


async def encerrar_engines() -> None:
    """Fecha os pools ja criados. Shutdown do lifespan e teardown de teste.

    Depois disso o proximo uso cria engines novas; necessario nos testes,
    onde cada asyncio.run tem seu proprio event loop e conexoes async nao
    podem atravessar loops.
    """
    for nome, obter in _ENGINES.items():
        if obter.cache_info().currsize:
            await obter().dispose()
            logger.info("Engine de %s encerrada", nome)
        obter.cache_clear()
    _fabrica_de_sessoes.cache_clear()
