"""Consultas e escritas sobre filtros de negocio reutilizaveis."""

from collections.abc import Sequence

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.models.filtro import Filtro
from src.observabilidade import logar_chamada


@logar_chamada
def buscar_por_id(sessao: Session, filtro_id: int) -> Filtro | None:
    return sessao.scalars(select(Filtro).where(Filtro.id == filtro_id)).one_or_none()


@logar_chamada
def buscar_por_nome(sessao: Session, tabela_id: int, nome: str) -> Filtro | None:
    # Usa a unique constraint (tabela_id, nome): upsert idempotente ao
    # popular o catalogo.
    return sessao.scalars(
        select(Filtro).where(Filtro.tabela_id == tabela_id, Filtro.nome == nome)
    ).one_or_none()


@logar_chamada
def listar_ativos_por_tabela(sessao: Session, tabela_id: int) -> Sequence[Filtro]:
    return sessao.scalars(
        select(Filtro).where(Filtro.tabela_id == tabela_id, Filtro.ativo.is_(True))
    ).all()


@logar_chamada
def listar_ativos_por_tabelas(sessao: Session, tabela_ids: list[int]) -> Sequence[Filtro]:
    # Variante em lote usada por get_filters, que recebe varias tabelas
    # escolhidas na mesma chamada.
    return sessao.scalars(
        select(Filtro).where(Filtro.tabela_id.in_(tabela_ids), Filtro.ativo.is_(True))
    ).all()


@logar_chamada
def criar(
    sessao: Session,
    tabela_id: int,
    nome: str,
    descricao: str,
    expressao_sql: str,
    quando_usar: str,
) -> Filtro:
    filtro = Filtro(
        tabela_id=tabela_id,
        nome=nome,
        descricao=descricao,
        expressao_sql=expressao_sql,
        quando_usar=quando_usar,
    )
    sessao.add(filtro)
    return filtro


@logar_chamada
def atualizar_regra(
    sessao: Session,
    filtro_id: int,
    descricao: str | None = None,
    expressao_sql: str | None = None,
    quando_usar: str | None = None,
) -> Filtro | None:
    # Os 3 campos sao not-null no schema: None aqui so significa "nao
    # alterar", sem ambiguidade com "setar NULL".
    filtro = buscar_por_id(sessao, filtro_id)
    if filtro is None:
        return None
    if descricao is not None:
        filtro.descricao = descricao
    if expressao_sql is not None:
        filtro.expressao_sql = expressao_sql
    if quando_usar is not None:
        filtro.quando_usar = quando_usar
    return filtro


@logar_chamada
def ativar(sessao: Session, filtro_id: int) -> None:
    sessao.execute(update(Filtro).where(Filtro.id == filtro_id).values(ativo=True))


@logar_chamada
def desativar(sessao: Session, filtro_id: int) -> None:
    sessao.execute(update(Filtro).where(Filtro.id == filtro_id).values(ativo=False))
