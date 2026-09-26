"""Lista das tools prontas para o ToolNode. graph.py importa TOOLS daqui."""

from src.tools.descricoes_tool import get_descriptions
from src.tools.execucao_sql_tool import execute_sql
from src.tools.filtros_tool import get_filters
from src.tools.schema_tool import get_schema

TOOLS = [get_schema, get_descriptions, get_filters, execute_sql]
