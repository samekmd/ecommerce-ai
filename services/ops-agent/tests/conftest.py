import asyncio
import os

import pytest

# Antes de qualquer import que carregue o config: variavel de ambiente vence
# o .env, entao nenhum teste envia trace nem busca prompt no Langfuse real,
# mesmo com as chaves preenchidas. Testes de observabilidade montam um
# cliente proprio com exporter em memoria.
os.environ["LANGFUSE_PUBLIC_KEY"] = ""

from ops_agent.config import obter_configuracao
from ops_agent.database import encerrar_engines, verificar_conexoes


def rodar(corrotina):
    """asyncio.run com teardown das engines: conexao async nao atravessa event loop."""

    async def _executar():
        try:
            return await corrotina
        finally:
            await encerrar_engines()

    return asyncio.run(_executar())


@pytest.fixture(scope="session")
def banco_disponivel():
    """Pula quem depende dos bancos locais (docker compose) se nao responderem."""
    obter_configuracao.cache_clear()
    try:
        estado = rodar(verificar_conexoes())
    except Exception as erro:
        pytest.skip(f"configuracao ou banco indisponivel: {erro}")
    if not all(estado.values()):
        pytest.skip(f"bancos inacessiveis: {estado}")
