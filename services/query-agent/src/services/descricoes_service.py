"""Regra de negocio por tras da tool get_descriptions."""

import logging
from collections import defaultdict

from sqlalchemy.orm import Session

from src.models.coluna import Coluna
from src.log_stdout import resumir_lista
from src.repositories import coluna_repository
from src.services import comum, log_service
from src.services.tipos import ColunaDetalhe, ResultadoDescricoes, TabelaDetalhada

logger = logging.getLogger(__name__)


def buscar_descricoes(
    sessao: Session,
    banco_id: int,
    tabela_ids: list[int],
    thread_id: str | None = None,
    pergunta: str | None = None,
) -> ResultadoDescricoes:
    with log_service.medir_e_registrar(
        sessao,
        "get_descriptions",
        thread_id,
        pergunta,
        {"banco_id": banco_id, "tabela_ids": tabela_ids},
    ) as ctx:
        banco, erro = comum.validar_banco_ativo(sessao, banco_id)
        if erro:
            ctx.sucesso, ctx.erro = False, erro
            logger.warning("get_descriptions: banco=%s invalido: %s", banco_id, erro)
            return ResultadoDescricoes(sucesso=False, erro=erro)

        erro = comum.validar_quantidade_tabelas(tabela_ids)
        if erro:
            ctx.sucesso, ctx.erro = False, erro
            logger.warning(
                "get_descriptions: banco=%s tabela_ids=%s rejeitado: %s",
                banco_id, resumir_lista(tabela_ids), erro,
            )
            return ResultadoDescricoes(sucesso=False, erro=erro)

        tabelas_validas, ids_nao_encontrados = comum.resolver_tabelas_do_banco(
            sessao, banco.id, tabela_ids
        )

        colunas = coluna_repository.listar_ativas_por_tabelas(
            sessao, [t.id for t in tabelas_validas]
        )
        colunas_por_tabela: dict[int, list[Coluna]] = defaultdict(list)
        for coluna in colunas:
            colunas_por_tabela[coluna.tabela_id].append(coluna)

        tabelas_detalhadas = [
            TabelaDetalhada(
                id=tabela.id,
                nome_qualificado=tabela.nome_qualificado,
                descricao=tabela.descricao,
                dominio=tabela.dominio,
                colunas=[
                    ColunaDetalhe(
                        id=c.id,
                        nome=c.nome,
                        tipo=c.tipo,
                        descricao=c.descricao,
                        is_pk=c.is_pk,
                        is_fk=c.is_fk,
                        referencia=c.referencia,
                        valores_exemplo=c.valores_exemplo,
                        nullable=c.nullable,
                        ordem=c.ordem,
                    )
                    for c in colunas_por_tabela[tabela.id]
                ],
            )
            for tabela in tabelas_validas
        ]

        ctx.linhas_retornadas = len(tabelas_detalhadas)
        logger.info(
            "get_descriptions: banco=%s tabelas=%d colunas_totais=%d nao_encontrados=%d",
            banco_id, len(tabelas_detalhadas), len(colunas), len(ids_nao_encontrados),
        )
        return ResultadoDescricoes(
            sucesso=True,
            tabelas=tabelas_detalhadas,
            ids_nao_encontrados=ids_nao_encontrados,
        )
