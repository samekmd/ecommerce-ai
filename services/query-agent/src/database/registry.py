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

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from src.config import configuracao

logger = logging.getLogger(__name__)

_engines: dict[str, Engine] = {}
_trava = threading.Lock()


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
        pool_pre_ping=True,
        # Teto de tempo por query no proprio servidor. Protege caso o
        # banco alvo em producao nao tenha o role com timeout configurado.
        connect_args={
            "options": f"-c statement_timeout={configuracao.statement_timeout_ms}"
        },
        future=True,
    )

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
        conexao.rollback()
        conexao.close()


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