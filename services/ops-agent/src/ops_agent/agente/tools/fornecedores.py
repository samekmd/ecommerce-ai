from pydantic_ai import ModelRetry, RunContext

from ops_agent.agente.deps import DependenciasAgente
from ops_agent.repositories import fornecedor as fornecedor_repository
from ops_agent.schemas.fornecedor import FornecedorResumo

TAMANHO_MINIMO_TERMO = 2


async def buscar_fornecedores(
    ctx: RunContext[DependenciasAgente], termo: str
) -> list[FornecedorResumo]:
    """Busca fornecedores ATIVOS cujo nome contem o termo; devolve poucos resultados.

    Use antes de preencher fornecedor_id de um produto. Lista vazia significa que o
    fornecedor nao esta cadastrado (ou esta inativo): antes de desistir, tente uma variacao
    (sem "Ltda"/"S.A.", so a marca). Se continuar vazia, fornecedor_id nulo, o nome em
    fornecedor_citado e um aviso.

    Args:
        termo: Parte do nome do fornecedor, como citado pelo usuario (ex.: "XYZ").
    """
    termo = termo.strip()
    if len(termo) < TAMANHO_MINIMO_TERMO:
        raise ModelRetry(f"Informe ao menos {TAMANHO_MINIMO_TERMO} letras do nome do fornecedor.")

    async with ctx.deps.abrir_sessao() as sessao:
        fornecedores = await fornecedor_repository.buscar_ativos(
            sessao, termo, ctx.deps.max_fornecedores
        )
    ctx.deps.fornecedores_vistos.update(f.id for f in fornecedores)
    return fornecedores
