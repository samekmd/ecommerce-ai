from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, LargeBinary, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ops_agent.models.base import Base


class ProdutoImagem(Base):
    """Imagem 1:1 do produto (04_produtos_imagens.sql). Bytes crus, nunca base64."""

    __tablename__ = "produtos_imagens"
    __table_args__ = (
        CheckConstraint(
            "mime IN ('image/jpeg', 'image/png', 'image/webp')",
            name="ck_produtos_imagens_mime_valido",
        ),
        CheckConstraint("tamanho_bytes > 0", name="ck_produtos_imagens_tamanho_positivo"),
        CheckConstraint(
            "tamanho_bytes = octet_length(conteudo)", name="ck_produtos_imagens_tamanho_coerente"
        ),
    )

    produto_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("produtos.id", ondelete="CASCADE"), primary_key=True
    )
    conteudo: Mapped[bytes] = mapped_column(LargeBinary)
    mime: Mapped[str] = mapped_column(Text)
    tamanho_bytes: Mapped[int] = mapped_column(Integer)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
