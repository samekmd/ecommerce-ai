"""Consultas e escritas sobre o catalogo de colunas."""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.models.coluna import Coluna
from src.observabilidade import logar_chamada


@logar_chamada
def buscar_por_id(sessao: Session, coluna_id: int) -> Coluna | None:
    return sessao.scalars(select(Coluna).where(Coluna.id == coluna_id)).one_or_none()


@logar_chamada
def listar_ativas_por_tabela(sessao: Session, tabela_id: int) -> Sequence[Coluna]:
    return sessao.scalars(
        select(Coluna)
        .where(Coluna.tabela_id == tabela_id, Coluna.ativo.is_(True))
        .order_by(Coluna.ordem)
    ).all()


@logar_chamada
def listar_ativas_por_tabelas(sessao: Session, tabela_ids: list[int]) -> Sequence[Coluna]:
    # Variante em lote usada por get_descriptions, que pede varias
    # tabelas escolhidas na mesma chamada.
    return sessao.scalars(
        select(Coluna)
        .where(Coluna.tabela_id.in_(tabela_ids), Coluna.ativo.is_(True))
        .order_by(Coluna.tabela_id, Coluna.ordem)
    ).all()


@logar_chamada
def criar(
    sessao: Session,
    tabela_id: int,
    nome: str,
    tipo: str,
    descricao: str | None = None,
    is_pk: bool = False,
    is_fk: bool = False,
    referencia: str | None = None,
    valores_exemplo: list[str] | None = None,
    nullable: bool = True,
    ordem: int | None = None,
) -> Coluna:
    coluna = Coluna(
        tabela_id=tabela_id,
        nome=nome,
        tipo=tipo,
        descricao=descricao,
        is_pk=is_pk,
        is_fk=is_fk,
        referencia=referencia,
        valores_exemplo=valores_exemplo,
        nullable=nullable,
        ordem=ordem,
    )
    sessao.add(coluna)
    return coluna


@logar_chamada
def criar_lote(sessao: Session, tabela_id: int, colunas: list[dict[str, Any]]) -> list[Coluna]:
    # Caminho real de popular uma tabela inteira de uma vez. flush()
    # devolve os objetos ja com id preenchido para quem chama.
    objetos = [Coluna(tabela_id=tabela_id, **dados) for dados in colunas]
    sessao.add_all(objetos)
    sessao.flush()
    return objetos


@logar_chamada
def atualizar_descricao(sessao: Session, coluna_id: int, descricao: str | None) -> Coluna | None:
    coluna = buscar_por_id(sessao, coluna_id)
    if coluna is None:
        return None
    coluna.descricao = descricao
    return coluna


@logar_chamada
def atualizar_tipo(sessao: Session, coluna_id: int, tipo: str) -> Coluna | None:
    coluna = buscar_por_id(sessao, coluna_id)
    if coluna is None:
        return None
    coluna.tipo = tipo
    return coluna


@logar_chamada
def atualizar_flags_chave(
    sessao: Session, coluna_id: int, is_pk: bool, is_fk: bool, referencia: str | None
) -> Coluna | None:
    # Agrupados numa unica funcao: referencia so faz sentido com
    # is_fk=True, separar em setters individuais permitiria estado
    # inconsistente.
    coluna = buscar_por_id(sessao, coluna_id)
    if coluna is None:
        return None
    coluna.is_pk = is_pk
    coluna.is_fk = is_fk
    coluna.referencia = referencia
    return coluna


@logar_chamada
def atualizar_valores_exemplo(
    sessao: Session, coluna_id: int, valores: list[str] | None
) -> Coluna | None:
    coluna = buscar_por_id(sessao, coluna_id)
    if coluna is None:
        return None
    coluna.valores_exemplo = valores
    return coluna


@logar_chamada
def atualizar_ordem(sessao: Session, coluna_id: int, ordem: int | None) -> Coluna | None:
    coluna = buscar_por_id(sessao, coluna_id)
    if coluna is None:
        return None
    coluna.ordem = ordem
    return coluna


@logar_chamada
def ativar(sessao: Session, coluna_id: int) -> None:
    sessao.execute(update(Coluna).where(Coluna.id == coluna_id).values(ativo=True))


@logar_chamada
def desativar(sessao: Session, coluna_id: int) -> None:
    sessao.execute(update(Coluna).where(Coluna.id == coluna_id).values(ativo=False))


@logar_chamada
def desativar_todas_por_tabela(sessao: Session, tabela_id: int) -> None:
    # UPDATE em massa: usado ao ressincronizar a descricao de uma
    # tabela (desativa tudo, depois criar_lote insere o estado atual),
    # mais simples que diff coluna a coluna.
    sessao.execute(update(Coluna).where(Coluna.tabela_id == tabela_id).values(ativo=False))
