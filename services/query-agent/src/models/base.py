from datetime import datetime 

from sqlalchemy import DateTime, FetchedValue, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column 

class Base(DeclarativeBase):
    """Base de todas as entidades do banco da aplicacao.
    Nao mapeia o banco alvo. As tabelas do alvo tem schema arbitrario,
    descoberto em runtime, e sao consultadas via text() no executor.
    """
 
class TimestampMixin:
    """Colunas de auditoria mantidas pelo banco, nao pela aplicacao.
 
    O DDL instala um trigger que atualiza atualizado_em em todo UPDATE.
    Por isso usamos server_default e server_onupdate=FetchedValue() em
    vez de default e onupdate do Python: assim o SQLAlchemy sabe que o
    valor vem do servidor e recarrega o atributo apos o flush, em vez de
    manter em memoria um valor desatualizado.
    """
 
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
 
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        server_onupdate=FetchedValue(),
    )

