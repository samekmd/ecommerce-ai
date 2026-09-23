"""Ponto de contato entre a aplicacao e o Langfuse.

Toda funcao aqui e inofensiva quando o tracing esta desligado, e
nenhuma deixa excecao escapar: observabilidade quebrada nao pode
derrubar a pergunta do usuario. E o unico lugar do projeto onde esse
tipo de defesa se justifica - o Langfuse e servico externo.
"""

import logging
from typing import Any

from src.config import configuracao
from src.database.executor import ResultadoConsulta
from src.observability.setup import obter_cliente, obter_handler
from src.observability.tags import tags_da_pergunta

logger = logging.getLogger(__name__)


def config_do_grafo(thread_id: str, banco_id: int) -> dict[str, Any]:
    """Config do grafo, com tracing acoplado quando houver credenciais.

    thread_id vira session_id no Langfuse: e o que agrupa as perguntas
    de uma mesma conversa num unico lugar.
    """
    config: dict[str, Any] = {
        "configurable": {"thread_id": thread_id, "banco_id": banco_id}
    }

    try:
        handler = obter_handler()
        if handler is None:
            return config
        config["callbacks"] = [handler]
        config["metadata"] = {
            "langfuse_session_id": thread_id,
            "langfuse_tags": tags_da_pergunta(banco_id),
            "banco_id": banco_id,
            # Sem isto a generation fica sem modelo no Langfuse: o SDK
            # nao consegue extrair o nome do ChatOpenRouter e cai neste
            # metadado (verificado - sem ele, model.name vem vazio).
            "ls_model_name": configuracao.openrouter_model,
        }
    except Exception:
        logger.exception("Falha ao montar tracing; seguindo sem observabilidade.")

    return config


def anotar_consulta(resultado: ResultadoConsulta, tentativa: int) -> None:
    """Enriquece o span da tool em curso com os dados da consulta.

    Cai no span certo porque o span OTel corrente dentro de uma tool
    rastreada pelo handler e o proprio span da tool, e porque quem
    chama roda na thread da tool (so a execucao do SQL vai para o pool).
    """
    cliente = obter_cliente()
    if cliente is None:
        return

    try:
        cliente.update_current_span(
            metadata={
                "tentativa": tentativa,
                "sucesso": resultado.sucesso,
                "linhas_retornadas": resultado.total_linhas,
                "truncado": resultado.truncado,
                "duracao_ms": resultado.duracao_ms,
            },
            level=None if resultado.sucesso else "ERROR",
            status_message=None if resultado.sucesso else resultado.erro,
        )
    except Exception:
        logger.exception("Falha ao anotar consulta no trace; seguindo sem isso.")
