"""Regra de negocio por tras da tool get_filters."""

import logging

from sqlalchemy.orm import Session

from src.observabilidade import resumir_lista
from src.repositories import filtro_repository
from src.services import comum, log_service
from src.services.tipos import FiltroDetalhe, ResultadoFiltros

logger = logging.getLogger(__name__)


def buscar_filtros(
    sessao: Session,
    banco_id: int,
    tabela_ids: list[int],
    thread_id: str | None = None,
    pergunta: str | None = None,
) -> ResultadoFiltros:
    with log_service.medir_e_registrar(
        sessao,
        "get_filters",
        thread_id,
        pergunta,
        {"banco_id": banco_id, "tabela_ids": tabela_ids},
    ) as ctx:
        banco, erro = comum.validar_banco_ativo(sessao, banco_id)
        if erro:
            ctx.sucesso, ctx.erro = False, erro
            logger.warning("get_filters: banco=%s invalido: %s", banco_id, erro)
            return ResultadoFiltros(sucesso=False, erro=erro)

        erro = comum.validar_quantidade_tabelas(tabela_ids)
        if erro:
            ctx.sucesso, ctx.erro = False, erro
            logger.warning(
                "get_filters: banco=%s tabela_ids=%s rejeitado: %s",
                banco_id, resumir_lista(tabela_ids), erro,
            )
            return ResultadoFiltros(sucesso=False, erro=erro)

        tabelas_validas, ids_nao_encontrados = comum.resolver_tabelas_do_banco(
            sessao, banco.id, tabela_ids
        )

        filtros = filtro_repository.listar_ativos_por_tabelas(
            sessao, [t.id for t in tabelas_validas]
        )
        filtros_detalhe = [
            FiltroDetalhe(
                id=f.id,
                tabela_id=f.tabela_id,
                nome=f.nome,
                descricao=f.descricao,
                expressao_sql=f.expressao_sql,
                quando_usar=f.quando_usar,
            )
            for f in filtros
        ]

        ctx.linhas_retornadas = len(filtros_detalhe)
        logger.info(
            "get_filters: banco=%s tabelas=%d filtros=%d nao_encontrados=%d",
            banco_id, len(tabelas_validas), len(filtros_detalhe), len(ids_nao_encontrados),
        )
        return ResultadoFiltros(
            sucesso=True,
            filtros=filtros_detalhe,
            ids_nao_encontrados=ids_nao_encontrados,
        )
