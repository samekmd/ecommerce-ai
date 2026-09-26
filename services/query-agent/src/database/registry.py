"""Registro de engines dos bancos alvo.

Diferente do banco da aplicacao, os bancos alvo nao sao conhecidos no
import: a chave de conexao vem da tabela bancos, consultada em runtime.
Este modulo resolve chave -> engine sob demanda e mantem cache, para nao
recriar pool a cada consulta.
"""

import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Connection, Engine

from src.config import configuracao

logger = logging.getLogger(__name__)

_engines: dict[str, Engine] = {}
_trava = threading.Lock()

TETO_DE_CONEXOES = configuracao.target_pool_size + configuracao.target_pool_max_overflow


def pid_do_backend(dbapi_connection: Any) -> object:
    """Pid do backend, ou '?' se a conexao ja nao responder.

    Os eventos de invalidacao recebem conexao morta, e uma excecao
    levantada dentro de um listener sobe pela maquinaria do pool.
    """
    try:
        return dbapi_connection.info.backend_pid
    except Exception:
        return "?"


def _registrar_eventos_de_pool(engine: Engine, chave_conexao: str) -> None:
    """Loga abertura, retirada, devolucao e invalidacao de conexao.

    Sem isso, pool esgotado e indistinguivel de query lenta: o codigo
    fica parado esperando vaga sem emitir sinal nenhum.
    """

    def estado() -> str:
        return f"{engine.pool.checkedout()}/{TETO_DE_CONEXOES} em uso"

    @event.listens_for(engine, "connect")
    def _ao_conectar(dbapi_connection: Any, _registro: Any) -> None:
        logger.info(
            "Conexao aberta em %s (pid=%s, %s)",
            chave_conexao, pid_do_backend(dbapi_connection), estado(),
        )

    @event.listens_for(engine, "checkout")
    def _ao_retirar(dbapi_connection: Any, _registro: Any, _proxy: Any) -> None:
        em_uso = engine.pool.checkedout()
        registrar = logger.warning if em_uso >= TETO_DE_CONEXOES else logger.info
        registrar(
            "Conexao retirada do pool de %s (pid=%s, %d/%d em uso)",
            chave_conexao, pid_do_backend(dbapi_connection), em_uso, TETO_DE_CONEXOES,
        )

    @event.listens_for(engine, "checkin")
    def _ao_devolver(dbapi_connection: Any, _registro: Any) -> None:
        logger.info(
            "Conexao devolvida ao pool de %s (pid=%s, %s)",
            chave_conexao, pid_do_backend(dbapi_connection), estado(),
        )

    @event.listens_for(engine, "invalidate")
    def _ao_invalidar(dbapi_connection: Any, _registro: Any, excecao: Any) -> None:
        logger.warning(
            "Conexao invalidada em %s (pid=%s, %s): %s",
            chave_conexao, pid_do_backend(dbapi_connection), estado(), excecao,
        )


def _criar_engine(chave_conexao: str) -> Engine:
    url = configuracao.url_do_banco_alvo(chave_conexao)

    engine = create_engine(
        url,
        # Nunca ligado para banco alvo: as queries vem do LLM e podem
        # ser longas. O registro util fica na tabela logs.
        echo=False,
        pool_size=configuracao.target_pool_size,
        max_overflow=configuracao.target_pool_max_overflow,
        pool_recycle=configuracao.target_pool_recycle,
        pool_timeout=configuracao.target_pool_timeout_segundos,
        pool_pre_ping=True,
        connect_args={
            # Sem isso, uma conexao que morre silenciosamente na rede
            # (idle no pool, container reiniciado, NAT/firewall
            # derrubando sem RST) trava o cliente num recv() sem prazo -
            # nem statement_timeout (so conta a partir do servidor
            # receber a query) nem pool_timeout (so cobre a espera por
            # uma vaga no pool) protegem contra isso.
            "connect_timeout": 10,
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 3,
            # statement_timeout: teto de tempo por query no proprio
            # servidor, protege caso o banco alvo em producao nao tenha
            # o role com timeout configurado. tcp_user_timeout: mesmo
            # orcamento, mas cobre a rede morrer durante uma query em
            # andamento (statement_timeout sozinho nao pega isso).
            "options": (
                f"-c statement_timeout={configuracao.statement_timeout_ms} "
                f"-c tcp_user_timeout={configuracao.statement_timeout_ms}"
            ),
        },
        future=True,
    )

    _registrar_eventos_de_pool(engine, chave_conexao)
    logger.info("Engine criada para banco alvo %s", chave_conexao)
    return engine


def obter_engine(chave_conexao: str) -> Engine:
    """Devolve a engine da chave, criando na primeira vez.

    Double-checked locking: o caminho quente evita a trava, e a trava
    so entra quando a engine ainda nao existe.
    """
    engine = _engines.get(chave_conexao)
    if engine is not None:
        return engine

    with _trava:
        engine = _engines.get(chave_conexao)
        if engine is None:
            engine = _criar_engine(chave_conexao)
            _engines[chave_conexao] = engine
        return engine


@contextmanager
def conexao_leitura(chave_conexao: str) -> Iterator[Connection]:
    """Conexao com transacao marcada como somente leitura.

    O usuario agente_leitura ja bloqueia escrita no nivel do banco. Esta
    e uma segunda camada, barata, que protege o caso em que o banco alvo
    de producao foi configurado sem o role correto.

    A transacao sempre termina em rollback: nao ha nada para persistir,
    e o rollback devolve a conexao ao pool em estado limpo.
    """
    engine = obter_engine(chave_conexao)
    conexao = engine.connect().execution_options(postgresql_readonly=True)
    try:
        yield conexao
    finally:
        # Numa conexao morta o rollback levanta, e sem estes try o
        # close() abaixo nao roda e a excecao de limpeza substitui o
        # desfecho real do bloco (medido: "the connection is closed"
        # chegando ao lugar de um resultado que ja tinha sido lido).
        try:
            conexao.rollback()
        except Exception as erro:
            logger.warning("Rollback falhou em %s: %s", chave_conexao, erro)
        try:
            conexao.close()
        except Exception as erro:
            logger.warning("Close falhou em %s: %s", chave_conexao, erro)


def verificar_conexao(chave_conexao: str) -> bool:
    """Checagem de saude de um banco alvo especifico."""
    try:
        with conexao_leitura(chave_conexao) as conexao:
            conexao.execute(text("SELECT 1"))
        return True
    except Exception as erro:
        logger.warning("Banco alvo %s inacessivel: %s", chave_conexao, erro)
        return False


def encerrar_engines() -> None:
    """Fecha todos os pools. Usado em teardown de teste e shutdown."""
    with _trava:
        for chave, engine in _engines.items():
            engine.dispose()
            logger.info("Engine encerrada: %s", chave)
        _engines.clear()


def engines_ativas() -> list[str]:
    """Chaves com engine ja instanciada. Util para diagnostico."""
    return sorted(_engines)