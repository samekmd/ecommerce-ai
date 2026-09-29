"""Models da auditoria no app_db (docker/init-app/02_ops_auditoria.sql).

Base separada da do banco de negocio: sao bancos diferentes e nenhum
metadata deve misturar as tabelas.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class BaseApp(DeclarativeBase):
    """Base declarativa das tabelas ops_* do app_db."""


class Interpretacao(BaseApp):
    __tablename__ = "ops_interpretacoes"
    __table_args__ = (
        CheckConstraint("(tipo IS NULL) <> (erro IS NULL)", name="ck_ops_interpretacoes_resultado"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    usuario: Mapped[str] = mapped_column(Text)
    mensagem: Mapped[str] = mapped_column(Text)
    modelo: Mapped[str] = mapped_column(Text)
    tipo: Mapped[str | None] = mapped_column(Text)
    proposta: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    erro: Mapped[str | None] = mapped_column(Text)
    duracao_ms: Mapped[int] = mapped_column(Integer)
    trace_id: Mapped[str | None] = mapped_column(Text)
    prompt_versao: Mapped[int | None] = mapped_column(Integer)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Cadastro(BaseApp):
    __tablename__ = "ops_cadastros"
    __table_args__ = (
        CheckConstraint(
            "entidade IN ('produto', 'fornecedor', 'categoria', 'cupom')",
            name="ck_ops_cadastros_entidade",
        ),
        CheckConstraint(
            "resultado IN ('criado', 'conflito', 'invalido', 'erro')",
            name="ck_ops_cadastros_resultado",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    interpretacao_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("ops_interpretacoes.id", ondelete="SET NULL")
    )
    usuario: Mapped[str] = mapped_column(Text)
    entidade: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    resultado: Mapped[str] = mapped_column(Text)
    entidade_id: Mapped[int | None] = mapped_column(Integer)
    campo_erro: Mapped[str | None] = mapped_column(Text)
    chave_idempotencia: Mapped[str | None] = mapped_column(Text)
    resposta: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
