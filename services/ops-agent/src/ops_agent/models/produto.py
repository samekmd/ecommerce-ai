from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from ops_agent.models.base import Base


class Produto(Base):
    __tablename__ = "produtos"
    __table_args__ = (
        UniqueConstraint("sku", name="uq_produtos_sku"),
        CheckConstraint("preco > 0", name="ck_produtos_preco_positivo"),
        CheckConstraint("estoque >= 0", name="ck_produtos_estoque_nao_negativo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    categoria_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("categorias.id", ondelete="RESTRICT")
    )
    fornecedor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("fornecedores.id", ondelete="RESTRICT")
    )
    nome: Mapped[str] = mapped_column(Text)
    sku: Mapped[str] = mapped_column(Text)
    # Decimal, nunca float: dinheiro.
    preco: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    estoque: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    ativo: Mapped[bool] = mapped_column(Boolean, server_default=true())
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
