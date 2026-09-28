from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from ops_agent.models.base import Base


class Categoria(Base):
    __tablename__ = "categorias"
    # Nomes identicos ao DDL: o service traduz violacao em erro de campo
    # pelo nome da constraint.
    __table_args__ = (
        UniqueConstraint("nome", name="uq_categorias_nome"),
        CheckConstraint(
            "categoria_pai_id IS NULL OR categoria_pai_id <> id",
            name="ck_categorias_pai_diferente_de_si",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(Text)
    categoria_pai_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("categorias.id", ondelete="SET NULL")
    )
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
