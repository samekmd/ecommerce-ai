"""Tool get_schema: primeiro estagio da recuperacao de contexto."""

import logging
from typing import Annotated

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from src.database.database import sessao_app
from src.services import schema_service
from src.tools import contexto, formatacao

logger = logging.getLogger(__name__)


@tool(parse_docstring=True)
def get_schema(
    config: RunnableConfig,
    state: Annotated[dict, InjectedState],
    dominio: str | None = None,
) -> str:
    """Lista as tabelas do banco alvo com nome e descricao de uma linha.

    Use primeiro, antes de get_descriptions, para decidir quais tabelas
    sao relevantes para a pergunta sem carregar o detalhe pesado de
    colunas.

    Args:
        dominio: filtra por dominio de negocio (ex.: 'vendas'). Omita
            para listar todas as tabelas ativas do banco.
    """
    # Alguns modelos mandam a string literal "none"/"null" em vez de
    # omitir um argumento opcional - trata como ausencia de filtro.
    if isinstance(dominio, str) and dominio.strip().lower() in {"none", "null", ""}:
        dominio = None

    banco_id = contexto.extrair_banco_id(config)
    thread_id = contexto.extrair_thread_id(config)
    pergunta = contexto.extrair_pergunta(state)

    logger.info("get_schema chamada: banco_id=%s dominio=%s", banco_id, dominio)

    with sessao_app() as sessao:
        resultado = schema_service.listar_schema(
            sessao, banco_id, dominio, thread_id, pergunta
        )

    return formatacao.formatar_schema(resultado)
