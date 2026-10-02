"""Engines e sessoes contra o target_db local (docker compose).

Cada teste roda num asyncio.run proprio e encerra as engines no fim:
conexoes async nao atravessam event loops.
"""

import asyncio
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from ops_agent.config import obter_configuracao
from ops_agent.database import (
    encerrar_engines,
    sessao_escrita,
    sessao_leitura,
    verificar_conexoes,
)


def rodar(corrotina_factory):
    async def _com_teardown():
        try:
            return await corrotina_factory()
        finally:
            await encerrar_engines()

    return asyncio.run(_com_teardown())


@pytest.fixture(scope="module", autouse=True)
def banco_disponivel():
    obter_configuracao.cache_clear()
    try:
        estado = rodar(verificar_conexoes)
    except Exception as erro:
        pytest.skip(f"configuracao ou banco indisponivel: {erro}")
    if not all(estado.values()):
        pytest.skip(f"target_db inacessivel: {estado}")


async def _contar_categorias(nome: str) -> int:
    async with sessao_leitura() as sessao:
        resultado = await sessao.execute(
            text("SELECT count(*) FROM categorias WHERE nome = :nome"), {"nome": nome}
        )
        return resultado.scalar_one()


def test_leitura_consulta_produtos():
    async def cenario():
        async with sessao_leitura() as sessao:
            return (await sessao.execute(text("SELECT count(*) FROM produtos"))).scalar_one()

    assert rodar(cenario) > 0


def test_leitura_recusa_escrita():
    async def cenario():
        async with sessao_leitura() as sessao:
            await sessao.execute(text("INSERT INTO categorias (nome) VALUES ('nunca')"))

    with pytest.raises(DBAPIError, match="read-only transaction"):
        rodar(cenario)


def test_escrita_sem_permissao_de_update():
    async def cenario():
        async with sessao_escrita() as sessao:
            await sessao.execute(text("UPDATE categorias SET nome = nome WHERE id = 1"))

    with pytest.raises(DBAPIError, match="permission denied"):
        rodar(cenario)


def test_escrita_insere_e_rollback_explicito_descarta():
    nome = f"teste-{uuid.uuid4()}"

    async def cenario():
        async with sessao_escrita() as sessao:
            novo_id = (
                await sessao.execute(
                    text("INSERT INTO categorias (nome) VALUES (:nome) RETURNING id"),
                    {"nome": nome},
                )
            ).scalar_one()
            await sessao.rollback()
        return novo_id, await _contar_categorias(nome)

    novo_id, total = rodar(cenario)
    assert novo_id > 0
    assert total == 0


def test_escrita_excecao_no_bloco_faz_rollback():
    nome = f"teste-{uuid.uuid4()}"

    class Falha(Exception):
        pass

    async def cenario():
        with pytest.raises(Falha):
            async with sessao_escrita() as sessao:
                await sessao.execute(
                    text("INSERT INTO categorias (nome) VALUES (:nome)"), {"nome": nome}
                )
                raise Falha
        return await _contar_categorias(nome)

    assert rodar(cenario) == 0


def test_verificar_conexoes_e_recriar_engine_apos_encerrar():
    async def cenario():
        primeira = await verificar_conexoes()
        await encerrar_engines()
        segunda = await verificar_conexoes()
        return primeira, segunda

    esperado = {"leitura": True, "escrita": True, "app": True}
    assert rodar(cenario) == (esperado, esperado)
