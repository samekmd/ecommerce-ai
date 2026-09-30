import os
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from ops_agent.config import ConfiguracaoInvalida, carregar_configuracao

SENHA = "senha_super_secreta"
CHAVE = "sk-or-chave-super-secreta"
CHAVE_GROQ = "gsk-chave-groq-super-secreta"

AMBIENTE_VALIDO = {
    "OPS_LEITURA_DATABASE_URL": f"postgresql://agente_leitura:{SENHA}@localhost:5434/loja",
    "OPS_ESCRITA_DATABASE_URL": f"postgresql://agente_escrita:{SENHA}@localhost:5434/loja",
    "APP_DATABASE_URL": f"postgresql+psycopg://text2sql:{SENHA}@localhost:5433/text2sql_app",
    "GROQ_API_KEY": CHAVE_GROQ,
    "OPS_MODELO_GROQ": "qwen/qwen3.8-27b",
    "OPENROUTER_API_KEY": CHAVE,
    "OPS_MODELO_OPENROUTER": "openai/gpt-4.1-mini",
}


@pytest.fixture(autouse=True)
def ambiente(monkeypatch):
    # Isola do ambiente real e do .env: so vale o que cada teste define.
    for nome in list(os.environ):
        if nome.startswith(("OPS_", "OPENROUTER_", "GROQ_", "APP_DATABASE", "LANGFUSE_", "AMBIENTE")):
            monkeypatch.delenv(nome)
    for nome, valor in AMBIENTE_VALIDO.items():
        monkeypatch.setenv(nome, valor)


def carregar():
    return carregar_configuracao(_env_file=None)


def test_ambiente_completo_carrega_sem_expor_segredos():
    config = carregar()

    assert config.ops_modelo_groq == "qwen/qwen3.8-27b"
    assert config.ops_modelo_openrouter == "openai/gpt-4.1-mini"
    assert config.groq_api_key.get_secret_value() == CHAVE_GROQ
    assert config.openrouter_api_key.get_secret_value() == CHAVE
    assert SENHA not in repr(config)
    assert CHAVE not in repr(config)
    assert CHAVE_GROQ not in repr(config)
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


def test_groq_e_obrigatorio(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY")

    with pytest.raises(ConfiguracaoInvalida, match="groq_api_key"):
        carregar()


def test_modelo_groq_padrao(monkeypatch):
    monkeypatch.delenv("OPS_MODELO_GROQ")

    assert carregar().ops_modelo_groq == "qwen/qwen3.8-27b"


def test_modelos_em_uso_com_fallback():
    config = carregar()

    assert config.modelo_principal == "groq:qwen/qwen3.8-27b"
    assert config.modelos_em_uso == "groq:qwen/qwen3.8-27b > openrouter:openai/gpt-4.1-mini"


@pytest.mark.parametrize("valor", [None, ""])
def test_sem_fallback_nao_exige_chave_do_openrouter(monkeypatch, valor):
    monkeypatch.delenv("OPENROUTER_API_KEY")
    if valor is None:
        monkeypatch.delenv("OPS_MODELO_OPENROUTER")
    else:
        monkeypatch.setenv("OPS_MODELO_OPENROUTER", valor)

    config = carregar()

    assert config.ops_modelo_openrouter is None
    assert config.modelos_em_uso == "groq:qwen/qwen3.8-27b"
    assert config.modelo_gratuito is False


def test_fallback_sem_chave_do_openrouter_falha(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY")

    with pytest.raises(ConfiguracaoInvalida, match="exige OPENROUTER_API_KEY"):
        carregar()


def test_modelo_gratuito_permitido_em_desenvolvimento(monkeypatch):
    monkeypatch.setenv("OPS_MODELO_OPENROUTER", "nvidia/nemotron-3-super-120b-a12b:free")

    assert carregar().modelo_gratuito is True


def test_modelo_pago_nao_e_gratuito():
    assert carregar().modelo_gratuito is False


@pytest.mark.parametrize(
    "modelo", ["nvidia/nemotron-3-super-120b-a12b:free", "openrouter/free", "stealth/qualquer"]
)
def test_modelo_gratuito_recusado_em_producao(monkeypatch, modelo):
    monkeypatch.setenv("AMBIENTE", "producao")
    monkeypatch.setenv("OPS_MODELO_OPENROUTER", modelo)

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
