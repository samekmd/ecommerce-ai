"""Catalogo de tabelas do banco alvo."""

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
    from src.models.banco import Banco
    from src.models.coluna import Coluna
    from src.models.filtro import Filtro


class Tabela(TimestampMixin, Base):
    __tablename__ = "tabelas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    banco_id: Mapped[int] = mapped_column(
        ForeignKey("bancos.id", ondelete="CASCADE"), nullable=False
    )

    nome: Mapped[str] = mapped_column(Text, nullable=False)
    schema_name: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="public"
    )

    # Resumo de uma linha, obrigatorio: e o que get_schema devolve para
    # o agente decidir relevancia sem carregar o catalogo inteiro.
    descricao: Mapped[str] = mapped_column(Text, nullable=False)

    # Gancho de escala: permite filtrar get_schema por area de negocio
    # quando o banco alvo tiver centenas de tabelas.
    dominio: Mapped[str | None] = mapped_column(Text)

    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    banco: Mapped["Banco"] = relationship(back_populates="tabelas")
    colunas: Mapped[list["Coluna"]] = relationship(
        back_populates="tabela",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Coluna.ordem",
    )
    filtros: Mapped[list["Filtro"]] = relationship(
        back_populates="tabela",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint("banco_id", "schema_name", "nome", name="uq_tabelas_identidade"),
        CheckConstraint(
            "length(trim(descricao)) > 0", name="ck_tabelas_descricao_nao_vazia"
        ),
        Index("ix_tabelas_banco", "banco_id", postgresql_where=text("ativo")),
        Index("ix_tabelas_dominio", "dominio", postgresql_where=text("ativo")),
    )

    @property
    def nome_qualificado(self) -> str:
        return f"{self.schema_name}.{self.nome}"

    def __repr__(self) -> str:
        return f"<Tabela {self.nome_qualificado}>"