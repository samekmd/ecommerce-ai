import re

from sqlalchemy import Numeric, cast, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ops_agent.models import Produto, ProdutoImagem
from ops_agent.schemas.produto import ProdutoCadastro

# Mesmo padrao do seed: SKU-000001.
DIGITOS_SKU = 6


async def existe_sku(sessao: AsyncSession, sku: str) -> bool:
    return bool(await sessao.scalar(select(exists().where(Produto.sku == sku))))


async def proximo_sku(sessao: AsyncSession, prefixo: str) -> str:
    """Proximo PREFIXO-NNNNNN livre, a partir do maior sufixo existente.

    E sugestao para o formulario, nao reserva: dois cadastros simultaneos
    podem receber o mesmo valor, e o UNIQUE resolve com 409 no campo sku.
    """
    regex = f"^{re.escape(prefixo)}-([0-9]+)$"
    # numeric e nao integer: um SKU manual com sufixo enorme estouraria o cast.
    sufixo = cast(func.substring(Produto.sku, regex), Numeric)
    maior = await sessao.scalar(select(func.max(sufixo)).where(Produto.sku.regexp_match(regex)))
    proximo = int(maior or 0) + 1
    return f"{prefixo}-{proximo:0{DIGITOS_SKU}d}"


async def inserir(sessao: AsyncSession, dados: ProdutoCadastro) -> Produto:
    """Grava o produto sem a imagem; o flush traz o id para inserir_imagem."""
    produto = Produto(**dados.model_dump(exclude={"imagem"}))
    sessao.add(produto)
    await sessao.flush()
    return produto


async def inserir_imagem(sessao: AsyncSession, produto_id: int, conteudo: bytes, mime: str) -> None:
    """Na mesma sessao do produto: os dois entram ou nenhum entra."""
    sessao.add(
        ProdutoImagem(
            produto_id=produto_id, conteudo=conteudo, mime=mime, tamanho_bytes=len(conteudo)
        )
    )
    await sessao.flush()
