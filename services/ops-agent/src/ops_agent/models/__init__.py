"""Models SQLAlchemy das 5 tabelas que o ops-agent toca, espelhando o DDL."""

from ops_agent.models.base import Base
from ops_agent.models.categoria import Categoria
from ops_agent.models.cupom import Cupom
from ops_agent.models.fornecedor import Fornecedor
from ops_agent.models.produto import Produto
from ops_agent.models.produto_imagem import ProdutoImagem

__all__ = ["Base", "Categoria", "Cupom", "Fornecedor", "Produto", "ProdutoImagem"]
