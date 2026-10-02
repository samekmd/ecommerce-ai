from pydantic_ai import RunContext

from ops_agent.agente.deps import DependenciasAgente
from ops_agent.repositories import categoria as categoria_repository
from ops_agent.schemas.categoria import CategoriaResumo


async def listar_categorias(ctx: RunContext[DependenciasAgente]) -> list[CategoriaResumo]:
    """Lista todas as categorias existentes com o caminho hierarquico ("Moda > Camisas").

    Use antes de preencher categoria_id de um produto ou categoria_pai_id de uma categoria.
    Prefira categorias com folha=true. Se nenhuma encaixar, deixe o ID nulo e sugira a
    categoria no aviso; nunca crie categoria implicitamente. Confianca baixa na escolha
    tambem vira aviso.
    """
    async with ctx.deps.abrir_sessao() as sessao:
        categorias = await categoria_repository.listar_com_caminho(sessao)
    ctx.deps.categorias_vistas.update(c.id for c in categorias)
    return categorias
