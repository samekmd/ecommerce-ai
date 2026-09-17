"""Detalhe de colunas, devolvido por get_descriptions."""

from typing import TYPE_CHECKING

from sqlalchemy import (
    ARRAY,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.models.tabela import Tabela


class Coluna(TimestampMixin, Base):
    __tablename__ = "colunas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tabela_id: Mapped[int] = mapped_column(
        ForeignKey("tabelas.id", ondelete="CASCADE"), nullable=False
    )

    nome: Mapped[str] = mapped_column(Text, nullable=False)
    tipo: Mapped[str] = mapped_column(Text, nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)

    is_pk: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_fk: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    referencia: Mapped[str | None] = mapped_column(Text)

    # Valores possiveis de colunas categoricas. E o campo que mais reduz
    # erro na pratica: sem ele o agente inventa valores em WHERE.
    valores_exemplo: Mapped[list[str] | None] = mapped_column(ARRAY(Text))

    # Nome coincide com o kwarg nullable do mapped_column, mas nao ha
    # conflito: um e atributo, o outro e parametro.
    nullable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )

    ordem: Mapped[int | None] = mapped_column(Integer)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    tabela: Mapped["Tabela"] = relationship(back_populates="colunas")

    __table_args__ = (
        UniqueConstraint("tabela_id", "nome", name="uq_colunas_tabela_nome"),
        Index("ix_colunas_tabela", "tabela_id", postgresql_where=text("ativo")),
    )

    def __repr__(self) -> str:
        return f"<Coluna {self.nome} {self.tipo}>"