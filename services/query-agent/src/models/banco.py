"""Bancos de dados alvo que o agente pode consultar."""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.models.tabela import Tabela


class Banco(TimestampMixin, Base):
    __tablename__ = "bancos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    nome: Mapped[str] = mapped_column(Text, nullable=False)

    # Nome da variavel de ambiente com a URL de conexao, nunca a URL em
    # si. Resolvido por config.url_do_banco_alvo(), que valida o formato
    # antes de tocar no ambiente.
    chave_conexao: Mapped[str] = mapped_column(Text, nullable=False)

    descricao: Mapped[str | None] = mapped_column(Text)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    # Nomeadas explicitamente: unique=True inline deixa o Postgres
    # auto-nomear (bancos_nome_key), divergindo do DDL. O Alembic
    # trataria como constraint diferente e tentaria recriar.
    __table_args__ = (
        UniqueConstraint("nome", name="uq_bancos_nome"),
        UniqueConstraint("chave_conexao", name="uq_bancos_chave_conexao"),
    )

    tabelas: Mapped[list["Tabela"]] = relationship(
        back_populates="banco",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Banco {self.nome} ({self.chave_conexao})>"