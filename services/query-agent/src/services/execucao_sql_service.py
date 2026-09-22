"""Regra de negocio por tras da tool execute_sql."""

import logging

from sqlalchemy.orm import Session

from src.database.executor import ResultadoConsulta, executar_consulta
from src.log_stdout import truncar_texto
from src.observability import tracing
from src.repositories import log_repository
from src.services import comum, log_service

logger = logging.getLogger(__name__)


def executar(
    sessao: Session,
    banco_id: int,
    sql: str,
    thread_id: str | None = None,
    pergunta: str | None = None,
) -> ResultadoConsulta:
    # Quantas vezes o agente ja tentou nesta conversa. Cada chamada ja
    # gerava uma linha em logs, mas nada dizia que eram tentativas
    # sucessivas do mesmo objetivo - da para ver o agente insistindo.
    tentativa = 1
    if thread_id:
        tentativa = log_repository.contar_por_thread_e_tool(sessao, thread_id, "execute_sql") + 1

    with log_service.medir_e_registrar(
        sessao,
        "execute_sql",
        thread_id,
        pergunta,
        {"banco_id": banco_id, "sql": sql, "tentativa": tentativa},
    ) as ctx:
        banco, erro = comum.validar_banco_ativo(sessao, banco_id)
        if erro:
            ctx.sucesso, ctx.erro, ctx.query_executada = False, erro, sql
            logger.warning("execute_sql: banco=%s invalido: %s", banco_id, erro)
            return ResultadoConsulta(sucesso=False, erro=erro, sql=sql)

        resultado = executar_consulta(banco.chave_conexao, sql)

        ctx.query_executada = resultado.sql or sql
        ctx.sucesso = resultado.sucesso
        ctx.erro = resultado.erro
        ctx.linhas_retornadas = resultado.total_linhas
        ctx.duracao_ms_override = resultado.duracao_ms

        tracing.anotar_consulta(resultado, tentativa)

        if not resultado.sucesso:
            logger.warning(
                "execute_sql: banco=%s tentativa=%d sql=%s falhou: %s",
                banco_id, tentativa, truncar_texto(sql), resultado.erro,
            )
        else:
            logger.info(
                "execute_sql: banco=%s tentativa=%d sql=%s linhas=%d duracao_ms=%d truncado=%s",
                banco_id, tentativa, truncar_texto(sql), resultado.total_linhas,
                resultado.duracao_ms, resultado.truncado,
            )
        return resultado
