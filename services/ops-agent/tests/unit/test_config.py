import os
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from ops_agent.config import ConfiguracaoInvalida, carregar_configuracao

SENHA = "senha_super_secreta"
CHAVE = "sk-or-chave-super-secreta"

AMBIENTE_VALIDO = {
    "OPS_LEITURA_DATABASE_URL": f"postgresql://agente_leitura:{SENHA}@localhost:5434/loja",
    "OPS_ESCRITA_DATABASE_URL": f"postgresql://agente_escrita:{SENHA}@localhost:5434/loja",
    "APP_DATABASE_URL": f"postgresql+psycopg://text2sql:{SENHA}@localhost:5433/text2sql_app",
    "OPENROUTER_API_KEY": CHAVE,
    "OPS_MODELO": "openai/gpt-4.1-mini",
}


@pytest.fixture(autouse=True)
def ambiente(monkeypatch):
    # Isola do ambiente real e do .env: so vale o que cada teste define.
    for nome in list(os.environ):
        if nome.startswith(("OPS_", "OPENROUTER_", "APP_DATABASE", "LANGFUSE_", "AMBIENTE")):
            monkeypatch.delenv(nome)
    for nome, valor in AMBIENTE_VALIDO.items():
        monkeypatch.setenv(nome, valor)


def carregar():
    return carregar_configuracao(_env_file=None)


def test_ambiente_completo_carrega_sem_expor_segredos():
    config = carregar()

    assert config.ops_modelo == "openai/gpt-4.1-mini"
    assert config.openrouter_api_key.get_secret_value() == CHAVE
    assert SENHA not in repr(config)
    assert CHAVE not in repr(config)
    assert SENHA not in str(config.model_dump())


def test_url_normalizada_para_psycopg3():
    config = carregar()

    url = config.ops_leitura_database_url.get_secret_value()
    assert url.startswith("postgresql+psycopg://agente_leitura:")


def test_postgres_curto_tambem_normalizado(monkeypatch):
    monkeypatch.setenv(
        "OPS_ESCRITA_DATABASE_URL", f"postgres://agente_escrita:{SENHA}@localhost:5434/loja"
    )

    url = carregar().ops_escrita_database_url.get_secret_value()
    assert url.startswith("postgresql+psycopg://")


def test_modelo_ausente_falha(monkeypatch):
    monkeypatch.delenv("OPS_MODELO")

    with pytest.raises(ConfiguracaoInvalida, match="ops_modelo"):
        carregar()


def test_modelo_gratuito_permitido_em_desenvolvimento(monkeypatch):
    monkeypatch.setenv("OPS_MODELO", "nvidia/nemotron-3-super-120b-a12b:free")

    assert carregar().modelo_gratuito is True


def test_modelo_pago_nao_e_gratuito():
    assert carregar().modelo_gratuito is False


@pytest.mark.parametrize(
    "modelo", ["nvidia/nemotron-3-super-120b-a12b:free", "openrouter/free", "stealth/qualquer"]
)
def test_modelo_gratuito_recusado_em_producao(monkeypatch, modelo):
    monkeypatch.setenv("AMBIENTE", "producao")
    monkeypatch.setenv("OPS_MODELO", modelo)

    with pytest.raises(ConfiguracaoInvalida, match="proibido em producao"):
        carregar()


def test_mesmo_role_em_leitura_e_escrita_falha(monkeypatch):
    monkeypatch.setenv("OPS_ESCRITA_DATABASE_URL", AMBIENTE_VALIDO["OPS_LEITURA_DATABASE_URL"])

    with pytest.raises(ConfiguracaoInvalida, match="roles diferentes"):
        carregar()


def test_erro_de_url_nao_vaza_senha(monkeypatch):
    monkeypatch.setenv("OPS_LEITURA_DATABASE_URL", f"mysql://agente_leitura:{SENHA}@host/loja")

    with pytest.raises(ConfiguracaoInvalida) as erro:
        carregar()

    assert SENHA not in str(erro.value)
    assert erro.value.__cause__ is None


def test_cors_separado_por_virgula(monkeypatch):
    monkeypatch.setenv("OPS_CORS_ORIGENS", "http://a.test, http://b.test,")

    assert carregar().ops_cors_origens == ["http://a.test", "http://b.test"]


def test_temperatura_alta_recusada(monkeypatch):
    monkeypatch.setenv("OPS_TEMPERATURA", "0.9")

    with pytest.raises(ConfiguracaoInvalida, match="ops_temperatura"):
        carregar()


def test_fuso_invalido_falha(monkeypatch):
    monkeypatch.setenv("OPS_FUSO_HORARIO", "America/Atlantida")

    with pytest.raises(ConfiguracaoInvalida, match="fuso"):
        carregar()


def test_hoje_usa_fuso_configurado():
    config = carregar()

    assert config.hoje() == datetime.now(ZoneInfo("America/Sao_Paulo")).date()


def test_langfuse_desligado_sem_chaves():
    assert carregar().langfuse_configurado is False
