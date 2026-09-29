"""Busca do system prompt no Langfuse, com cliente falso (sem rede)."""

import logging
from types import SimpleNamespace

import pytest

from ops_agent.agente.prompts import sistema


class ClienteFalso:
    def __init__(self, resposta=None, erro=None):
        self.resposta = resposta
        self.erro = erro
        self.chamadas = []

    def get_prompt(self, nome, **kwargs):
        self.chamadas.append((nome, kwargs))
        if self.erro:
            raise self.erro
        return self.resposta


def prompt_do_langfuse(versao=3, fallback=False):
    return SimpleNamespace(
        name=sistema.NOME_PROMPT_SISTEMA,
        prompt=f"PROMPT v{versao}",
        version=versao,
        labels=["production"],
        is_fallback=fallback,
    )


@pytest.fixture(autouse=True)
def zerar_log_de_versao(monkeypatch):
    monkeypatch.setattr(sistema, "_ultima_versao_logada", None)


def test_sem_cliente_usa_texto_embutido(monkeypatch):
    monkeypatch.setattr(sistema, "obter_cliente", lambda: None)

    prompt = sistema.obter_prompt_sistema()

    assert prompt.texto == sistema.PROMPT_SISTEMA_PADRAO
    assert prompt.versao is None
    assert prompt.cliente is None


def test_versao_de_producao_do_langfuse(monkeypatch):
    cliente = ClienteFalso(prompt_do_langfuse(versao=3))
    monkeypatch.setattr(sistema, "obter_cliente", lambda: cliente)

    prompt = sistema.obter_prompt_sistema()

    assert prompt.texto == "PROMPT v3"
    assert prompt.versao == 3
    assert prompt.cliente is cliente.resposta
    nome, kwargs = cliente.chamadas[0]
    assert nome == "ops_agente_sistema"
    assert kwargs["label"] == "production"
    assert kwargs["fallback"] == sistema.PROMPT_SISTEMA_PADRAO


def test_fallback_do_sdk_nao_tem_versao(monkeypatch):
    # O SDK devolve o fallback com version=0; ligar a generation a ele
    # atribuiria metrica a uma versao inexistente.
    monkeypatch.setattr(
        sistema, "obter_cliente", lambda: ClienteFalso(prompt_do_langfuse(versao=0, fallback=True))
    )

    prompt = sistema.obter_prompt_sistema()

    assert prompt.texto == sistema.PROMPT_SISTEMA_PADRAO
    assert prompt.versao is None
    assert prompt.cliente is None


def test_erro_do_sdk_nunca_escapa(monkeypatch):
    monkeypatch.setattr(sistema, "obter_cliente", lambda: ClienteFalso(erro=RuntimeError("fora")))

    assert sistema.obter_prompt_sistema() is sistema.PROMPT_EMBUTIDO


def test_troca_de_versao_logada_uma_vez(monkeypatch, caplog):
    cliente = ClienteFalso(prompt_do_langfuse(versao=3))
    monkeypatch.setattr(sistema, "obter_cliente", lambda: cliente)

    with caplog.at_level(logging.INFO, logger=sistema.__name__):
        sistema.obter_prompt_sistema()
        sistema.obter_prompt_sistema()
        cliente.resposta = prompt_do_langfuse(versao=4)
        sistema.obter_prompt_sistema()

    mensagens = [r.getMessage() for r in caplog.records if "em uso" in r.getMessage()]
    assert len(mensagens) == 2
    assert "v3" in mensagens[0] and "v4" in mensagens[1]
