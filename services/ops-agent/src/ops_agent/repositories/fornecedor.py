from sqlalchemy import case, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ops_agent.models import Fornecedor
from ops_agent.schemas.fornecedor import FornecedorCadastro, FornecedorResumo


def _escapar_like(termo: str) -> str:
    # Sem isso, termo "%" viraria curinga e devolveria a tabela inteira.
    return termo.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def buscar_ativos(sessao: AsyncSession, termo: str, limite: int) -> list[FornecedorResumo]:
    """Ativos cujo nome contem o termo; quem comeca com ele vem primeiro.

    Sem pg_trgm no banco, ILIKE e a similaridade disponivel. O limite e
    obrigatorio: a tool nunca devolve a tabela inteira ao LLM.
    """
    padrao = _escapar_like(termo.strip())
    consulta = (
        select(Fornecedor.id, Fornecedor.nome, Fornecedor.cidade, Fornecedor.estado)
        .where(Fornecedor.ativo, Fornecedor.nome.ilike(f"%{padrao}%", escape="\\"))
        .order_by(
            case((Fornecedor.nome.ilike(f"{padrao}%", escape="\\"), 0), else_=1),
            func.length(Fornecedor.nome),
            Fornecedor.nome,
        )
        .limit(limite)
    )
    linhas = (await sessao.execute(consulta)).mappings()
    return [FornecedorResumo.model_validate(linha) for linha in linhas]


async def existe_ativo(sessao: AsyncSession, fornecedor_id: int) -> bool:
    consulta = exists().where(Fornecedor.id == fornecedor_id, Fornecedor.ativo)
    return bool(await sessao.scalar(select(consulta)))


async def existe_cnpj(sessao: AsyncSession, cnpj: str) -> bool:
    return bool(await sessao.scalar(select(exists().where(Fornecedor.cnpj == cnpj))))


async def inserir(sessao: AsyncSession, dados: FornecedorCadastro) -> Fornecedor:
    fornecedor = Fornecedor(**dados.model_dump())
    sessao.add(fornecedor)
    await sessao.flush()
    return fornecedor
