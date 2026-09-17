"""Validacoes internas compartilhadas entre as services.

Nao e chamado por tools - so pelos outros arquivos de services/.
"""

import logging

from sqlalchemy.orm import Session

from src.config import configuracao
from src.models.banco import Banco
from src.models.tabela import Tabela
from src.repositories import banco_repository, tabela_repository

logger = logging.getLogger(__name__)


def validar_banco_ativo(sessao: Session, banco_id: int) -> tuple[Banco | None, str | None]:
    banco = banco_repository.buscar_por_id(sessao, banco_id)
    if banco is None:
        motivo = f"Banco {banco_id} nao encontrado."
        logger.debug("validar_banco_ativo: banco=%s invalido: %s", banco_id, motivo)
        return None, motivo
    if not banco.ativo:
        motivo = f"Banco {banco_id} esta desativado."
        logger.debug("validar_banco_ativo: banco=%s invalido: %s", banco_id, motivo)
        return None, motivo
    return banco, None


def validar_quantidade_tabelas(tabela_ids: list[int]) -> str | None:
    if not tabela_ids:
        erro = "Informe ao menos uma tabela."
        logger.debug("validar_quantidade_tabelas: rejeitado: %s", erro)
        return erro
    if len(tabela_ids) > configuracao.max_tabelas_por_chamada:
        erro = (
            f"Foram pedidas {len(tabela_ids)} tabelas, o maximo por "
            f"chamada e {configuracao.max_tabelas_por_chamada}."
        )
        logger.debug("validar_quantidade_tabelas: rejeitado: %s", erro)
        return erro
    return None


def resolver_tabelas_do_banco(
    sessao: Session, banco_id: int, tabela_ids: list[int]
) -> tuple[list[Tabela], list[int]]:
    # Deduplica preservando a ordem de pedido do LLM.
    ids_unicos = list(dict.fromkeys(tabela_ids))

    tabelas = tabela_repository.listar_detalhada_por_ids(sessao, ids_unicos)
    # so ativas e do banco pedido: defesa contra tabela_id vazado de
    # outra conversa/banco, ja que listar_detalhada_por_ids nao filtra
    # por banco_id.
    tabelas_por_id = {
        t.id: t for t in tabelas if t.banco_id == banco_id
    }

    tabelas_validas = [tabelas_por_id[i] for i in ids_unicos if i in tabelas_por_id]
    ids_nao_encontrados = [i for i in ids_unicos if i not in tabelas_por_id]
    logger.debug(
        "resolver_tabelas_do_banco: banco=%s pedidas=%d validas=%d nao_encontradas=%s",
        banco_id, len(ids_unicos), len(tabelas_validas), ids_nao_encontrados,
    )
    return tabelas_validas, ids_nao_encontrados
