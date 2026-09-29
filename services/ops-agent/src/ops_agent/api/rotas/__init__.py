from ops_agent.api.rotas import (
    categorias,
    cupons,
    fornecedores,
    interpretar,
    produtos,
    saude,
)

# Rotas de negocio, montadas sob /api/v1; saude fica na raiz.
ROUTERS_V1 = [
    interpretar.router,
    produtos.router,
    fornecedores.router,
    categorias.router,
    cupons.router,
]

__all__ = ["ROUTERS_V1", "saude"]
