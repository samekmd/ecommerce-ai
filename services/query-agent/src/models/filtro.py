"""Regras de negocio reutilizaveis expressas em SQL."""

from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
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


class Filtro(TimestampMixin, Base):
    __tablename__ = "filtros"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tabela_id: Mapped[int] = mapped_column(
        ForeignKey("tabelas.id", ondelete="CASCADE"), nullable=False
    )

    nome: Mapped[str] = mapped_column(Text, nullable=False)
    descricao: Mapped[str] = mapped_column(Text, nullable=False)

    # Predicado aplicavel em WHERE, ex: status = 'ativo' AND deletado_em IS NULL
    expressao_sql: Mapped[str] = mapped_column(Text, nullable=False)

    # Instrucao para o LLM sobre quando aplicar. Sem este campo o agente
    # ve uma lista de filtros e nao tem criterio para escolher.
    quando_usar: Mapped[str] = mapped_column(Text, nullable=False)

    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    tabela: Mapped["Tabela"] = relationship(back_populates="filtros")

    __table_args__ = (
        UniqueConstraint("tabela_id", "nome", name="uq_filtros_tabela_nome"),
        CheckConstraint(
            "length(trim(expressao_sql)) > 0", name="ck_filtros_expressao_nao_vazia"
        ),
        Index("ix_filtros_tabela", "tabela_id", postgresql_where=text("ativo")),
    )

    def __repr__(self) -> str:
        return f"<Filtro {self.nome}>"