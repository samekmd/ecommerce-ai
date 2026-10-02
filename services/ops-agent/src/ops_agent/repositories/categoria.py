from sqlalchemy import exists, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ops_agent.models import Categoria
from ops_agent.schemas.categoria import CategoriaCadastro, CategoriaResumo

# Parte das raizes: uma categoria num ciclo (A -> B -> A) nunca e
# alcancada, entao a recursao termina mesmo com dado corrompido.
_SQL_ARVORE = text(
    """
    WITH RECURSIVE arvore AS (
        SELECT id, nome AS caminho
        FROM categorias
        WHERE categoria_pai_id IS NULL
        UNION ALL
        SELECT filha.id, arvore.caminho || ' > ' || filha.nome
        FROM categorias AS filha
        JOIN arvore ON filha.categoria_pai_id = arvore.id
    )
    SELECT
        arvore.id,
        arvore.caminho,
        NOT EXISTS (
            SELECT 1 FROM categorias AS neta WHERE neta.categoria_pai_id = arvore.id
        ) AS folha
    FROM arvore
    ORDER BY arvore.caminho
    """
)


async def listar_com_caminho(sessao: AsyncSession) -> list[CategoriaResumo]:
    linhas = (await sessao.execute(_SQL_ARVORE)).mappings()
    return [CategoriaResumo.model_validate(linha) for linha in linhas]


async def existe(sessao: AsyncSession, categoria_id: int) -> bool:
    return bool(await sessao.scalar(select(exists().where(Categoria.id == categoria_id))))


async def existe_nome(sessao: AsyncSession, nome: str) -> bool:
    # O UNIQUE do banco diferencia caixa: "Camisas" e "camisas" passariam.
    consulta = exists().where(func.lower(Categoria.nome) == nome.strip().lower())
    return bool(await sessao.scalar(select(consulta)))


async def obter_nome(sessao: AsyncSession, categoria_id: int) -> str | None:
    return await sessao.scalar(select(Categoria.nome).where(Categoria.id == categoria_id))


async def inserir(sessao: AsyncSession, dados: CategoriaCadastro) -> Categoria:
    categoria = Categoria(**dados.model_dump())
    sessao.add(categoria)
    await sessao.flush()
    return categoria
