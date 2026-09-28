from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base declarativa. Os models espelham o DDL; este servico nao cria nem migra schema."""
