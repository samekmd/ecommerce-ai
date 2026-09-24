"""Consultas e escritas sobre o catalogo de bancos alvo."""

from collections.abc import Sequence

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.models.banco import Banco
from src.log_stdout import logar_chamada


@logar_chamada
def buscar_por_id(sessao: Session, banco_id: int) -> Banco | None:
    return sessao.scalars(select(Banco).where(Banco.id == banco_id)).one_or_none()


@logar_chamada
def buscar_por_nome(sessao: Session, nome: str) -> Banco | None:
    return sessao.scalars(select(Banco).where(Banco.nome == nome)).one_or_none()


@logar_chamada
def buscar_por_chave_conexao(sessao: Session, chave_conexao: str) -> Banco | None:
    return sessao.scalars(
        select(Banco).where(Banco.chave_conexao == chave_conexao)
    ).one_or_none()


@logar_chamada
def listar_ativos(sessao: Session) -> Sequence[Banco]:
    return sessao.scalars(
        select(Banco).where(Banco.ativo.is_(True)).order_by(Banco.nome)
    ).all()


@logar_chamada
def listar_todos(sessao: Session) -> Sequence[Banco]:
    return sessao.scalars(select(Banco).order_by(Banco.nome)).all()


@logar_chamada
def criar(sessao: Session, nome: str, chave_conexao: str, descricao: str | None = None) -> Banco:
    banco = Banco(nome=nome, chave_conexao=chave_conexao, descricao=descricao)
    sessao.add(banco)
    # flush: o populamento do catalogo cria as Tabelas do banco em
    # seguida, na mesma transacao, e precisa de banco.id.
    sessao.flush()
    return banco


@logar_chamada
def atualizar_dados(
    sessao: Session,
    banco_id: int,
    nome: str | None = None,
    chave_conexao: str | None = None,
) -> Banco | None:
    banco = buscar_por_id(sessao, banco_id)
    if banco is None:
        return None
    if nome is not None:
        banco.nome = nome
    if chave_conexao is not None:
        banco.chave_conexao = chave_conexao
    return banco


@logar_chamada
def atualizar_descricao(sessao: Session, banco_id: int, descricao: str | None) -> Banco | None:
    # Setter dedicado: descricao e anulavel, None aqui e valor valido.
    banco = buscar_por_id(sessao, banco_id)
    if banco is None:
        return None
    banco.descricao = descricao
    return banco


@logar_chamada
def ativar(sessao: Session, banco_id: int) -> None:
    sessao.execute(update(Banco).where(Banco.id == banco_id).values(ativo=True))


@logar_chamada
def desativar(sessao: Session, banco_id: int) -> None:
    sessao.execute(update(Banco).where(Banco.id == banco_id).values(ativo=False))
