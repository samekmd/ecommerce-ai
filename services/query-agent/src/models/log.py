"""Registro de execucao das tools do agente."""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class Log(Base):
    """Log de uma chamada de tool.

    Sem FK para as demais entidades de proposito: o historico precisa
    sobreviver a alteracoes e remocoes no catalogo de metadados.

    Nao usa TimestampMixin porque um log nunca e atualizado depois de
    gravado, entao atualizado_em nao faria sentido.
    """

    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # Agrupa todas as chamadas de uma mesma conversa do agente.
    thread_id: Mapped[str | None] = mapped_column(Text)
    pergunta: Mapped[str | None] = mapped_column(Text)

    tool_name: Mapped[str] = mapped_column(Text, nullable=False)
    argumentos: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    query_executada: Mapped[str | None] = mapped_column(Text)

    sucesso: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    erro: Mapped[str | None] = mapped_column(Text)

    linhas_retornadas: Mapped[int | None] = mapped_column(Integer)
    duracao_ms: Mapped[int | None] = mapped_column(Integer)

    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_logs_thread", "thread_id", "criado_em"),
        Index("ix_logs_criado_em", text("criado_em DESC")),
        # Indice parcial so das falhas: a tabela cresce rapido e a
        # consulta de diagnostico quase sempre filtra por erro.
        Index("ix_logs_falhas", text("criado_em DESC"), postgresql_where=text("NOT sucesso")),
    )

    def __repr__(self) -> str:
        marca = "ok" if self.sucesso else "erro"
        return f"<Log {self.tool_name} ({marca}) {self.duracao_ms}ms>"