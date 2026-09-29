"""Tools somente leitura do agente. Cada uma abre e fecha a propria sessao."""

from ops_agent.agente.tools.categorias import listar_categorias
from ops_agent.agente.tools.cupons import verificar_codigo_cupom
from ops_agent.agente.tools.fornecedores import buscar_fornecedores

TOOLS = [listar_categorias, buscar_fornecedores, verificar_codigo_cupom]

__all__ = ["TOOLS", "buscar_fornecedores", "listar_categorias", "verificar_codigo_cupom"]
