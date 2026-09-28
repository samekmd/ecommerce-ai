"""Repositories contra o target_db local.

Tudo roda em sessao_escrita e termina em rollback explicito: o banco de
teste nao fica com resto de cadastro.
"""

import asyncio
import base64
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from ops_agent.config import obter_configuracao
from ops_agent.database import encerrar_engines, sessao_escrita, verificar_conexoes
from ops_agent.models import ProdutoImagem
from ops_agent.repositories import categoria, cupom, fornecedor, produto
from ops_agent.schemas.produto import ProdutoCadastro

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def rodar(cenario):
    """Executa cenario(sessao) numa transacao desfeita no fim."""

    async def _executar():
        try:
            async with sessao_escrita() as sessao:
                resultado = await cenario(sessao)
                await sessao.rollback()
                return resultado
        finally:
            await encerrar_engines()

    return asyncio.run(_executar())


@pytest.fixture(scope="module", autouse=True)
def banco_disponivel():
    obter_configuracao.cache_clear()

    async def verificar():
        try:
            return await verificar_conexoes()
        finally:
            await encerrar_engines()

    try:
        estado = asyncio.run(verificar())
    except Exception as erro:
        pytest.skip(f"configuracao ou banco indisponivel: {erro}")
    if not all(estado.values()):
        pytest.skip(f"target_db inacessivel: {estado}")


# --- categoria ----------------------------------------------------------


def test_listar_com_caminho_monta_hierarquia():
    async def cenario(sessao):
        return await categoria.listar_com_caminho(sessao)

    categorias = rodar(cenario)
    caminhos = {c.caminho: c for c in categorias}
    assert "Moda" in caminhos
    assert caminhos["Moda"].folha is False
    assert any(c.caminho.startswith("Moda > ") and c.folha for c in categorias)


def test_existe_nome_ignora_caixa():
    async def cenario(sessao):
        return (
            await categoria.existe_nome(sessao, "moda"),
            await categoria.existe_nome(sessao, "nao-existe-" + uuid.uuid4().hex),
        )

    assert rodar(cenario) == (True, False)


def test_existe_e_obter_nome():
    async def cenario(sessao):
        return await categoria.existe(sessao, 1), await categoria.obter_nome(sessao, 1)

    existe, nome = rodar(cenario)
    assert existe is True
    assert nome


# --- fornecedor ---------------------------------------------------------


def test_buscar_ativos_respeita_limite_e_prioriza_prefixo():
    async def cenario(sessao):
        return await fornecedor.buscar_ativos(sessao, "casa", 3)

    resultado = rodar(cenario)
    assert 0 < len(resultado) <= 3
    assert resultado[0].nome.lower().startswith("casa")


def test_buscar_ativos_escapa_curinga():
    async def cenario(sessao):
        return await fornecedor.buscar_ativos(sessao, "%", 50)

    assert rodar(cenario) == []


def test_existe_ativo_e_cnpj():
    async def cenario(sessao):
        ativo = await fornecedor.buscar_ativos(sessao, "", 1)
        return (
            await fornecedor.existe_ativo(sessao, ativo[0].id),
            await fornecedor.existe_ativo(sessao, 999_999),
            await fornecedor.existe_cnpj(sessao, "00000000000001"),
        )

    assert rodar(cenario) == (True, False, True)


# --- produto ------------------------------------------------------------


def test_proximo_sku_segue_o_maior_sufixo():
    async def cenario(sessao):
        return (
            await produto.proximo_sku(sessao, "SKU"),
            await produto.proximo_sku(sessao, "ZZZ"),
        )

    proximo, novo_prefixo = rodar(cenario)
    assert proximo.startswith("SKU-") and int(proximo[4:]) > 500
    assert novo_prefixo == "ZZZ-000001"


def test_inserir_produto_e_imagem_na_mesma_transacao():
    sku = f"TST-{uuid.uuid4().hex[:8]}"

    async def cenario(sessao):
        dados = ProdutoCadastro(
            nome="Camisa teste",
            sku=sku,
            preco=Decimal("100.00"),
            estoque=5,
            categoria_id=1,
            fornecedor_id=1,
            imagem={"conteudo_base64": base64.b64encode(PNG).decode()},
        )
        criado = await produto.inserir(sessao, dados)
        await produto.inserir_imagem(sessao, criado.id, dados.imagem.conteudo, dados.imagem.mime)
        imagem = await sessao.scalar(
            select(ProdutoImagem).where(ProdutoImagem.produto_id == criado.id)
        )
        return criado.id, criado.ativo, await produto.existe_sku(sessao, sku), imagem.tamanho_bytes

    produto_id, ativo, sku_existe, tamanho = rodar(cenario)
    assert produto_id > 0
    assert ativo is True
    assert sku_existe is True
    assert tamanho == len(PNG)


# --- cupom --------------------------------------------------------------


def test_existe_codigo_ignora_caixa():
    async def cenario(sessao):
        return (
            await cupom.existe_codigo(sessao, "cupom0001"),
            await cupom.existe_codigo(sessao, "NAO-EXISTE-" + uuid.uuid4().hex[:6]),
        )

    assert rodar(cenario) == (True, False)
