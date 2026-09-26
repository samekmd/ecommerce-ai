"""Regra de negocio por tras da tool get_schema."""

import logging

from sqlalchemy.orm import Session

from src.repositories import tabela_repository
from src.services import comum, log_service
from src.services.tipos import ResultadoSchema, TabelaResumo

logger = logging.getLogger(__name__)


def listar_schema(
    sessao: Session,
    banco_id: int,
    dominio: str | None = None,
    thread_id: str | None = None,
    pergunta: str | None = None,
) -> ResultadoSchema:
    with log_service.medir_e_registrar(
        sessao, "get_schema", thread_id, pergunta, {"banco_id": banco_id, "dominio": dominio}
    ) as ctx:
        banco, erro = comum.validar_banco_ativo(sessao, banco_id)
        if erro:
            ctx.sucesso, ctx.erro = False, erro
            logger.warning("get_schema: banco=%s invalido: %s", banco_id, erro)
            return ResultadoSchema(sucesso=False, erro=erro)

        tabelas = tabela_repository.listar_resumo_por_banco(sessao, banco.id, dominio)
        resumo = [
            TabelaResumo(id=t.id, nome_qualificado=t.nome_qualificado, descricao=t.descricao)
            for t in tabelas
        ]

        ctx.linhas_retornadas = len(resumo)
        logger.info(
            "get_schema: banco=%s dominio=%s -> %d tabelas", banco_id, dominio, len(resumo)
        )
        return ResultadoSchema(sucesso=True, tabelas=resumo)
