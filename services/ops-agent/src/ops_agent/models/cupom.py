from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from ops_agent.models.base import Base


class Cupom(Base):
    __tablename__ = "cupons"
    __table_args__ = (
        UniqueConstraint("codigo", name="uq_cupons_codigo"),
        CheckConstraint(
            "percentual_desconto > 0 AND percentual_desconto <= 100",
            name="ck_cupons_percentual_valido",
        ),
        CheckConstraint("validade_fim >= validade_inicio", name="ck_cupons_validade_coerente"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(Text)
    percentual_desconto: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    validade_inicio: Mapped[date] = mapped_column(Date)
    validade_fim: Mapped[date] = mapped_column(Date)
    ativo: Mapped[bool] = mapped_column(Boolean, server_default=true())
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
