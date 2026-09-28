from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, Text, UniqueConstraint, func, true
from sqlalchemy.orm import Mapped, mapped_column

from ops_agent.models.base import Base


class Fornecedor(Base):
    __tablename__ = "fornecedores"
    __table_args__ = (
        UniqueConstraint("cnpj", name="uq_fornecedores_cnpj"),
        CheckConstraint("char_length(estado) = 2", name="ck_fornecedores_estado_sigla"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(Text)
    cnpj: Mapped[str] = mapped_column(Text)
    email_contato: Mapped[str | None] = mapped_column(Text)
    telefone: Mapped[str | None] = mapped_column(Text)
    cidade: Mapped[str] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(Text)
    ativo: Mapped[bool] = mapped_column(Boolean, server_default=true())
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
