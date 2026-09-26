"""Tool get_filters: filtros de negocio pre-aprovados por tabela."""

import logging
from typing import Annotated

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from src.database.database import sessao_app
from src.log_stdout import resumir_lista
from src.services import filtros_service
from src.tools import contexto, formatacao

logger = logging.getLogger(__name__)


@tool(parse_docstring=True)
def get_filters(
    config: RunnableConfig,
    state: Annotated[dict, InjectedState],
    tabela_ids: list[int],
) -> str:
    """Lista filtros de negocio aplicaveis as tabelas indicadas.

    Cada filtro traz a expressao SQL pronta e a instrucao de quando
    aplica-la (ex.: excluir cancelados por padrao). Use antes de montar
    a query em execute_sql.

    Args:
        tabela_ids: ids de tabela (campo 'id' de get_schema).
    """
    banco_id = contexto.extrair_banco_id(config)
    thread_id = contexto.extrair_thread_id(config)
    pergunta = contexto.extrair_pergunta(state)

    logger.info(
        "get_filters chamada: banco_id=%s tabela_ids=%s",
        banco_id, resumir_lista(tabela_ids),
    )

    with sessao_app() as sessao:
        resultado = filtros_service.buscar_filtros(
            sessao, banco_id, tabela_ids, thread_id, pergunta
        )

    return formatacao.formatar_filtros(resultado)
