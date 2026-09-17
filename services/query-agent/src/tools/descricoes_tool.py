"""Tool get_descriptions: segundo estagio, detalhe pesado por tabela."""

import logging
from typing import Annotated

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from src.database.database import sessao_app
from src.observabilidade import resumir_lista
from src.services import descricoes_service
from src.tools import contexto, formatacao

logger = logging.getLogger(__name__)


@tool(parse_docstring=True)
def get_descriptions(
    config: RunnableConfig,
    state: Annotated[dict, InjectedState],
    tabela_ids: list[int],
) -> str:
    """Detalha colunas, tipos e valores de exemplo das tabelas indicadas.

    Chame so com os ids devolvidos por get_schema, depois de decidir
    quais tabelas importam para a pergunta.

    Args:
        tabela_ids: ids de tabela (campo 'id' de get_schema). Maximo por
            chamada limitado pela configuracao do agente.
    """
    banco_id = contexto.extrair_banco_id(config)
    thread_id = contexto.extrair_thread_id(config)
    pergunta = contexto.extrair_pergunta(state)

    logger.info(
        "get_descriptions chamada: banco_id=%s tabela_ids=%s",
        banco_id, resumir_lista(tabela_ids),
    )

    with sessao_app() as sessao:
        resultado = descricoes_service.buscar_descricoes(
            sessao, banco_id, tabela_ids, thread_id, pergunta
        )

    return formatacao.formatar_descricoes(resultado)
