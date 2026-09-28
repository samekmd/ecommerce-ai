"""Configuracao central do ops-agent.

Unica fonte de verdade para variaveis de ambiente. Nenhum outro modulo
deve ler os.environ ou o .env diretamente.
"""

import logging
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy.engine import make_url

# O .env da raiz do monorepo e compartilhado com o query-agent; um .env
# local ao servico, se existir, prevalece (o ultimo da tupla vence).
# Caminhos absolutos para o servico subir de qualquer diretorio.
_RAIZ_SERVICO = Path(__file__).resolve().parents[2]
_RAIZ_MONOREPO = _RAIZ_SERVICO.parents[1]
_ARQUIVOS_ENV = (_RAIZ_MONOREPO / ".env", _RAIZ_SERVICO / ".env")

logger = logging.getLogger(__name__)


class ConfiguracaoInvalida(RuntimeError):
    """Erro de configuracao detectado na subida da aplicacao."""


def _normalizar_url(url: str) -> str:
    """Garante o dialeto psycopg3 na URL de conexao.

    Copiado do query-agent. A mensagem de erro nunca inclui a URL: ela
    carrega a senha do banco.
    """
    url = url.strip()
    if url.startswith("postgresql+"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    raise ValueError("URL de banco em formato nao reconhecido (esperado postgresql://...)")


class Configuracao(BaseSettings):
    # Campos sem env_prefix global: os proprios do servico levam ops_ no
    # nome porque o .env e compartilhado e o query-agent ja usa, por
    # exemplo, OPENROUTER_MODEL com um modelo :free.
    model_config = SettingsConfigDict(
        env_file=_ARQUIVOS_ENV,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------------------------------------------------------------
    # Ambiente
    # ---------------------------------------------------------------
    ambiente: str = "desenvolvimento"
    log_level: str = "INFO"

    # ---------------------------------------------------------------
    # Bancos. SecretStr porque as URLs carregam senha: repr e log mostram
    # asteriscos. Leitura (tools) e escrita (services) sao roles
    # distintos por restricao do projeto, conferido em _validar_roles.
    # ---------------------------------------------------------------
    ops_leitura_database_url: SecretStr
    ops_escrita_database_url: SecretStr
    # Auditoria de propostas e confirmacoes; mesmo banco da aplicacao do
    # query-agent.
    app_database_url: SecretStr

    ops_pool_size: int = Field(default=3, gt=0)
    ops_pool_max_overflow: int = Field(default=2, ge=0)
    ops_pool_recycle: int = 1800
    # Sem isso vale o default de 30s do SQLAlchemy, e pool esgotado trava
    # a requisicao sem erro nem log (medido no query-agent).
    ops_pool_timeout_segundos: int = Field(default=5, gt=0)
    # Transacao de cadastro e curta por desenho; passar disso e bug.
    ops_statement_timeout_segundos: int = Field(default=10, gt=0)
    sql_echo: bool = False

    # ---------------------------------------------------------------
    # LLM via OpenRouter
    # ---------------------------------------------------------------
    openrouter_api_key: SecretStr
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    # Obrigatorio e sem default: a escolha do modelo decide se tool
    # calling e saida estruturada funcionam.
    ops_modelo: str
    ops_temperatura: float = Field(default=0.0, ge=0.0, le=0.3)
    # Proposta estruturada com avisos passa facil dos 512 do query-agent.
    ops_max_tokens: int = Field(default=2048, gt=0)
    ops_timeout_llm_segundos: int = Field(default=60, gt=0)

    # ---------------------------------------------------------------
    # Agente
    # ---------------------------------------------------------------
    # Novas tentativas quando o validador de saida rejeita um ID que nao
    # veio de nenhuma tool.
    ops_retries_saida: int = Field(default=2, ge=0)
    ops_limite_requisicoes: int = Field(default=8, gt=0)
    ops_max_fornecedores_busca: int = Field(default=5, gt=0)
    # A data injetada no agente resolve "ate o fim do mes" e o inicio
    # padrao do cupom; em UTC o dia viraria as 21h de Brasilia.
    ops_fuso_horario: str = "America/Sao_Paulo"

    # ---------------------------------------------------------------
    # Imagem do produto. O limite fica aqui e nao em CHECK no DDL para
    # poder mudar sem migracao.
    # ---------------------------------------------------------------
    ops_imagem_max_bytes: int = Field(default=2 * 1024 * 1024, gt=0)

    # ---------------------------------------------------------------
    # API. NoDecode: no ambiente a lista vem separada por virgula, nao
    # como JSON.
    # ---------------------------------------------------------------
    ops_cors_origens: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    # ---------------------------------------------------------------
    # Langfuse (tracing; futuramente o system prompt). Mesma conta do
    # query-agent, por isso sem prefixo.
    # ---------------------------------------------------------------
    langfuse_public_key: str = ""
    langfuse_secret_key: SecretStr = SecretStr("")
    langfuse_base_url: str = "https://us.cloud.langfuse.com"
    langfuse_tracing_enabled: bool = True

    # ---------------------------------------------------------------
    @field_validator("ambiente")
    @classmethod
    def _validar_ambiente(cls, valor: str) -> str:
        permitidos = {"desenvolvimento", "homologacao", "producao"}
        if valor not in permitidos:
            raise ValueError(f"ambiente deve ser um de {sorted(permitidos)}")
        return valor

    @field_validator("log_level")
    @classmethod
    def _validar_log_level(cls, valor: str) -> str:
        nivel = valor.strip().upper()
        permitidos = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if nivel not in permitidos:
            raise ValueError(f"log_level deve ser um de {sorted(permitidos)}")
        return nivel

    @field_validator("ops_leitura_database_url", "ops_escrita_database_url", "app_database_url")
    @classmethod
    def _validar_url(cls, valor: SecretStr) -> SecretStr:
        url = valor.get_secret_value()
        if not url.strip():
            raise ValueError("URL de banco nao pode ser vazia")
        return SecretStr(_normalizar_url(url))

    @field_validator("openrouter_api_key")
    @classmethod
    def _validar_chave(cls, valor: SecretStr) -> SecretStr:
        if not valor.get_secret_value().strip():
            raise ValueError("OPENROUTER_API_KEY nao pode ser vazia")
        return valor

    @field_validator("ops_modelo")
    @classmethod
    def _validar_modelo(cls, valor: str) -> str:
        modelo = valor.strip()
        if not modelo:
            raise ValueError("OPS_MODELO nao pode ser vazio")
        return modelo

    @field_validator("ops_fuso_horario")
    @classmethod
    def _validar_fuso(cls, valor: str) -> str:
        try:
            ZoneInfo(valor)
        except (ZoneInfoNotFoundError, ValueError) as erro:
            raise ValueError(f"fuso horario desconhecido: {valor!r}") from erro
        return valor

    @field_validator("ops_cors_origens", mode="before")
    @classmethod
    def _separar_origens(cls, valor: Any) -> Any:
        if isinstance(valor, str):
            return [origem.strip() for origem in valor.split(",") if origem.strip()]
        return valor

    @model_validator(mode="after")
    def _validar_roles(self) -> "Configuracao":
        # Roles separados sao a protecao real: se as tools pudessem
        # escrever, "o agente nunca escreve" viraria so uma promessa do
        # prompt.
        leitura = make_url(self.ops_leitura_database_url.get_secret_value()).username
        escrita = make_url(self.ops_escrita_database_url.get_secret_value()).username
        if leitura == escrita:
            raise ValueError("URLs de leitura e escrita devem usar roles diferentes")
        return self

    @model_validator(mode="after")
    def _validar_modelo_gratuito(self) -> "Configuracao":
        # Provedores gratuitos podem reter e treinar com os prompts, e as
        # frases trazem nomes de fornecedores e CNPJs.
        if self.modelo_gratuito and self.em_producao:
            raise ValueError("modelos gratuitos podem usar os prompts; proibido em producao")
        return self

    # ---------------------------------------------------------------
    @property
    def em_producao(self) -> bool:
        return self.ambiente == "producao"

    @property
    def modelo_gratuito(self) -> bool:
        # openrouter/free e stealth/* tem preco zero sem o sufixo :free.
        return (
            self.ops_modelo.endswith(":free")
            or self.ops_modelo == "openrouter/free"
            or self.ops_modelo.startswith("stealth/")
        )

    @property
    def langfuse_configurado(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key.get_secret_value())

    @property
    def fuso(self) -> ZoneInfo:
        return ZoneInfo(self.ops_fuso_horario)

    def hoje(self) -> date:
        """Data atual no fuso do negocio, injetada no agente."""
        return datetime.now(self.fuso).date()


def carregar_configuracao(**valores: Any) -> Configuracao:
    """Instancia a configuracao traduzindo erro de validacao.

    include_input=False: o valor rejeitado pode ser uma URL com senha ou
    a chave da API, e a mensagem vai parar em log e traceback.
    """
    try:
        return Configuracao(**valores)
    except ValidationError as erro:
        detalhes = "; ".join(
            f"{'.'.join(str(parte) for parte in item['loc']) or 'configuracao'}: {item['msg']}"
            for item in erro.errors(include_input=False, include_url=False)
        )
        raise ConfiguracaoInvalida(f"Falha ao carregar configuracao: {detalhes}") from None


@lru_cache(maxsize=1)
def obter_configuracao() -> Configuracao:
    """Instancia unica, cacheada.

    Nao ha instancia criada no import: testes do agente importam modulos
    sem precisar de um ambiente completo.
    """
    configuracao = carregar_configuracao()
    if configuracao.modelo_gratuito:
        # Gratuitos falham com mais frequencia em tool calling e saida
        # estruturada; o aviso poupa tempo depurando prompt a toa.
        logger.warning(
            "Modelo gratuito em uso (%s): rate limit baixo e tool calling instavel",
            configuracao.ops_modelo,
        )
    return configuracao
