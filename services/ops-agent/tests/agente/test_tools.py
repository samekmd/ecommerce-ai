"""Tools chamadas direto, contra o target_db. So usam ctx.deps."""

import uuid
from types import SimpleNamespace

import pytest
from pydantic_ai import ModelRetry

from ops_agent.agente.tools import buscar_fornecedores, listar_categorias, verificar_codigo_cupom
from tests.conftest import rodar

pytestmark = pytest.mark.usefixtures("banco_disponivel")


def ctx(deps):
    return SimpleNamespace(deps=deps)


def test_listar_categorias_enxuto_e_registra_ids(deps):
    categorias = rodar(listar_categorias(ctx(deps)))

    assert len(categorias) >= 20
    assert set(categorias[0].model_dump()) == {"id", "caminho", "folha"}
    assert any(" > " in c.caminho for c in categorias)
    assert deps.categorias_vistas == {c.id for c in categorias}


def test_buscar_fornecedores_limita_e_registra_ids(deps):
    fornecedores = rodar(buscar_fornecedores(ctx(deps), "casa"))

    assert 0 < len(fornecedores) <= deps.max_fornecedores
    assert deps.fornecedores_vistos == {f.id for f in fornecedores}


def test_buscar_fornecedores_termo_curto_pede_retry(deps):
    with pytest.raises(ModelRetry, match="2 letras"):
        rodar(buscar_fornecedores(ctx(deps), " x "))


def test_buscar_fornecedores_inexistente_nao_registra(deps):
    assert rodar(buscar_fornecedores(ctx(deps), "inexistente-zzz")) == []
    assert deps.fornecedores_vistos == set()


def test_verificar_codigo_existente_normaliza(deps):
    resultado = rodar(verificar_codigo_cupom(ctx(deps), " cupom0001 "))
    assert resultado.model_dump() == {"codigo": "CUPOM0001", "formato_valido": True, "existe": True}


def test_verificar_codigo_novo(deps):
    codigo = f"NOVO{uuid.uuid4().hex[:6]}"
    resultado = rodar(verificar_codigo_cupom(ctx(deps), codigo))
    assert resultado.formato_valido is True
    assert resultado.existe is False


def test_verificar_codigo_formato_invalido_nao_consulta(deps):
    def proibido():
        raise AssertionError("nao deveria abrir sessao")

    deps.abrir_sessao = proibido
    resultado = rodar(verificar_codigo_cupom(ctx(deps), "black 10"))
    assert resultado.model_dump() == {"codigo": "BLACK 10", "formato_valido": False, "existe": False}
