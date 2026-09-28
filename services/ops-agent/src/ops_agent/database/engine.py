"""Fabrica comum das engines assincronas do banco de negocio.

Leitura e escrita usam roles diferentes e, portanto, engines e pools
diferentes; o que muda entre elas e so a URL. Nenhuma query mora aqui.
"""

import logging
from typing import Any

from pydantic import SecretStr
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from ops_agent.config import obter_configuracao

logger = logging.getLogger(__name__)


def _pid_do_backend(dbapi_connection: Any) -> object:
    """Pid do backend, ou '?' se a conexao ja nao responder.

    Os eventos de invalidacao recebem conexao morta, e uma excecao
    levantada dentro de um listener sobe pela maquinaria do pool.
    """
    try:
        return dbapi_connection.info.backend_pid
    except Exception:
        return "?"


def _registrar_eventos_de_pool(engine: AsyncEngine, nome: str, teto: int) -> None:
    """Avisa pool no teto e conexao invalidada.

    Sem isso, pool esgotado e indistinguivel de query lenta: a requisicao
    fica parada esperando vaga sem emitir sinal nenhum. So os eventos
    anormais sao logados; checkout/checkin a cada tool call seria ruido.
    """
    # Eventos de pool so existem na engine sincrona por baixo da async.
    sincrona = engine.sync_engine

    @event.listens_for(sincrona, "checkout")
    def _ao_retirar(dbapi_connection: Any, _registro: Any, _proxy: Any) -> None:
        em_uso = sincrona.pool.checkedout()
        if em_uso >= teto:
            logger.warning(
                "Pool de %s no teto (pid=%s, %d/%d em uso)",
                nome, _pid_do_backend(dbapi_connection), em_uso, teto,
            )

    @event.listens_for(sincrona, "invalidate")
    def _ao_invalidar(dbapi_connection: Any, _registro: Any, excecao: Any) -> None:
        logger.warning(
            "Conexao invalidada em %s (pid=%s): %s",
            nome, _pid_do_backend(dbapi_connection), excecao,
        )


def criar_engine(url: SecretStr, nome: str) -> AsyncEngine:
    configuracao = obter_configuracao()
    timeout_ms = configuracao.ops_statement_timeout_segundos * 1000

    engine = create_async_engine(
        url.get_secret_value(),
        echo=configuracao.sql_echo,
        pool_size=configuracao.ops_pool_size,
        max_overflow=configuracao.ops_pool_max_overflow,
        pool_recycle=configuracao.ops_pool_recycle,
        pool_timeout=configuracao.ops_pool_timeout_segundos,
        pool_pre_ping=True,
        connect_args={
            # Conexao que morre em silencio na rede (container reiniciado,
            # NAT derrubando sem RST) travaria num recv() sem prazo:
            # statement_timeout so conta depois que o servidor recebe a
            # query, e pool_timeout so cobre a espera por vaga.
            "connect_timeout": 10,
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 3,
            # idle_in_transaction e a trava no servidor para "nunca
            # transacao aberta enquanto o LLM responde": se alguem
            # esquecer uma sessao aberta durante o agent.run, o Postgres
            # derruba em vez de segurar locks. Repetido aqui porque o
            # banco de producao pode nao ter os ALTER ROLE do fixture.
            "options": (
                f"-c statement_timeout={timeout_ms} "
                f"-c idle_in_transaction_session_timeout={timeout_ms} "
                f"-c tcp_user_timeout={timeout_ms}"
            ),
        },
    )

    teto = configuracao.ops_pool_size + configuracao.ops_pool_max_overflow
    _registrar_eventos_de_pool(engine, nome, teto)
    logger.info("Engine de %s criada", nome)
    return engine
