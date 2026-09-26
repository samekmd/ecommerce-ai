"""Tool execute_sql: unico ponto de execucao de SQL escrito pelo LLM."""

import logging
from typing import Annotated

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from src.database.database import sessao_app
from src.log_stdout import truncar_texto
from src.services import execucao_sql_service
from src.tools import contexto, formatacao

logger = logging.getLogger(__name__)


@tool(parse_docstring=True)
def execute_sql(
    config: RunnableConfig,
    state: Annotated[dict, InjectedState],
    sql: str,
) -> str:
    """Executa uma consulta SELECT/WITH somente leitura no banco alvo.

    Erros de SQL voltam como texto de erro, nao como excecao: leia a
    mensagem e corrija a query na proxima chamada.

    Args:
        sql: consulta SQL, apenas SELECT ou WITH. Sem ponto e virgula
            multiplo.
    """
    banco_id = contexto.extrair_banco_id(config)
    thread_id = contexto.extrair_thread_id(config)
    pergunta = contexto.extrair_pergunta(state)

    logger.info("execute_sql chamada: banco_id=%s sql=%s", banco_id, truncar_texto(sql))

    with sessao_app() as sessao:
        resultado = execucao_sql_service.executar(
            sessao, banco_id, sql, thread_id, pergunta
        )

    return formatacao.formatar_consulta(resultado)
