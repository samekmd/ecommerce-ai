from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ops_agent.models import Cupom
from ops_agent.schemas.cupom import CupomCadastro


async def existe_codigo(sessao: AsyncSession, codigo: str) -> bool:
    # upper() dos dois lados: cupons antigos podem ter sido gravados fora
    # do padrao maiusculo, e o UNIQUE do banco diferencia caixa.
    consulta = exists().where(func.upper(Cupom.codigo) == codigo.strip().upper())
    return bool(await sessao.scalar(select(consulta)))


async def inserir(sessao: AsyncSession, dados: CupomCadastro) -> Cupom:
    cupom = Cupom(**dados.model_dump())
    sessao.add(cupom)
    await sessao.flush()
    return cupom
