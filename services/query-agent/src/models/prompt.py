"""Prompts do sistema, versionados."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class Prompt(TimestampMixin, Base):
    __tablename__ = "prompts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    chave: Mapped[str] = mapped_column(Text, nullable=False)
    conteudo: Mapped[str] = mapped_column(Text, nullable=False)
    versao: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    descricao: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("chave", "versao", name="uq_prompts_chave_versao"),
        CheckConstraint("versao > 0", name="ck_prompts_versao_positiva"),
        CheckConstraint(
            "length(trim(conteudo)) > 0", name="ck_prompts_conteudo_nao_vazio"
        ),
        # Indice unico parcial: garante no maximo uma versao ativa por
        # chave. Trocar de versao em producao vira uma transacao com
        # dois UPDATE, reversivel na hora.
        Index(
            "uq_prompts_um_ativo_por_chave",
            "chave",
            unique=True,
            postgresql_where=text("ativo"),
        ),
    )

    def __repr__(self) -> str:
        marca = "ativo" if self.ativo else "inativo"
        return f"<Prompt {self.chave} v{self.versao} ({marca})>"