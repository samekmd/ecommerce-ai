"""Regra de negocio por tras da tool execute_sql."""

import logging

from sqlalchemy.orm import Session

from src.database.executor import ResultadoConsulta, executar_consulta
from src.observabilidade import truncar_texto
from src.services import comum, log_service

logger = logging.getLogger(__name__)


def executar(
    sessao: Session,
    banco_id: int,
    sql: str,
    thread_id: str | None = None,
    pergunta: str | None = None,
) -> ResultadoConsulta:
    with log_service.medir_e_registrar(
        sessao, "execute_sql", thread_id, pergunta, {"banco_id": banco_id, "sql": sql}
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

        if not resultado.sucesso:
            logger.warning(
                "execute_sql: banco=%s sql=%s falhou: %s",
                banco_id, truncar_texto(sql), resultado.erro,
            )
        else:
            logger.info(
                "execute_sql: banco=%s sql=%s linhas=%d duracao_ms=%d truncado=%s",
                banco_id, truncar_texto(sql), resultado.total_linhas,
                resultado.duracao_ms, resultado.truncado,
            )
        return resultado
