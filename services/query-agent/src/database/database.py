from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import configuracao

app_db_engine = create_engine(
    configuracao.app_database_url,
    pool_pre_ping=True,
    future=True,
)

SessaoApp = sessionmaker(
    bind=app_db_engine,
    expire_on_commit=False,
    autoflush=False,
)

@contextmanager 
def sessao_app() -> Iterator[Session]:
    """Escopo transacional de uma unidade de trabalho.
 
    Deve envolver UMA chamada de tool, nunca o loop inteiro do grafo.
    Entre duas tool calls existe uma chamada ao LLM que pode levar
    segundos; manter a transacao aberta nesse intervalo esbarra no
    idle_in_transaction_session_timeout do servidor.
 
    A conexao sai do pool ja na entrada do bloco (begin + connection):
    pool esgotado ou banco fora do ar estoura aqui, nao no meio de um
    repository. O BEGIN no servidor continua saindo no primeiro
    statement - o psycopg3 nao emite antes disso.

    Uso:
        with sessao_app() as sessao:
            prompt = prompt_repository.buscar_ativo(sessao, "sql_agent_system")
    """
    sessao = SessaoApp()
    sessao.begin()
    sessao.connection()
    try:
        yield sessao
        sessao.commit()
    except Exception:
        sessao.rollback()
        raise
    finally:
        sessao.close()


def verificar_conexao() -> bool:
    """Checagem de saude usada na subida da aplicacao."""
    from sqlalchemy import text
 
    try:
        with app_db_engine.connect() as conexao:
            conexao.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
 
 
def encerrar_engine() -> None:
    """Fecha o pool. Usado em teardown de teste e shutdown."""
    app_db_engine.dispose()
