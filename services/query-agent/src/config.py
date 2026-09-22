"""Configuracao central da aplicacao.

Unica fonte de verdade para variaveis de ambiente. Nenhum outro modulo
deve chamar os.getenv ou load_dotenv diretamente.
"""

import os
import re
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# As chaves dos bancos alvo sao dinamicas: vem da coluna
# bancos.chave_conexao, entao nao existem como campos deste modelo.
# O Pydantic le o .env mas nao o exporta para os.environ, o que deixaria
# os.getenv("TARGET_DB_...") sempre None. Carregar aqui e o unico ponto
# do projeto que toca no .env; variaveis reais do ambiente tem
# precedencia, porque load_dotenv nao sobrescreve por padrao.
load_dotenv()

# Bancos alvo sao resolvidos dinamicamente a partir da coluna
# bancos.chave_conexao. O prefixo obrigatorio impede que um registro
# malformado no banco aponte para uma variavel sensivel como GROQ_API_KEY.
PREFIXO_BANCO_ALVO = "TARGET_DB_"
FORMATO_CHAVE_CONEXAO = re.compile(r"^TARGET_DB_[A-Z0-9_]+$")


class ConfiguracaoInvalida(RuntimeError):
    """Erro de configuracao detectado na subida da aplicacao."""


def _normalizar_url(url: str) -> str:
    """Garante o dialeto psycopg3 na URL de conexao.

    URLs vindas de outros sistemas costumam chegar como 'postgresql://',
    que o SQLAlchemy resolve para psycopg2. Como o projeto usa psycopg3,
    normalizamos aqui em vez de exigir formato exato no .env.
    """
    url = url.strip()
    if url.startswith("postgresql+"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    raise ConfiguracaoInvalida(
        f"URL de banco em formato nao reconhecido: {url[:30]}..."
    )


class Configuracao(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------------------------------------------------------------
    # Ambiente
    # ---------------------------------------------------------------
    ambiente: str = Field(default="desenvolvimento")

    # ---------------------------------------------------------------
    # Banco da aplicacao
    # ---------------------------------------------------------------
    app_database_url: str

    app_pool_size: int = 5
    app_pool_max_overflow: int = 5
    app_pool_recycle: int = 1800

    # ---------------------------------------------------------------
    # Bancos alvo
    # Pool menor: poucas queries, porem longas. Recycle mais agressivo
    # porque em producao o alvo costuma estar atras de firewall que
    # derruba conexao ociosa sem aviso.
    # ---------------------------------------------------------------
    target_pool_size: int = 2
    target_pool_max_overflow: int = 3
    target_pool_recycle: int = 900
    # Sem isso vale o default de 30s do SQLAlchemy, e pool esgotado
    # bloqueia todo esse tempo sem log nem erro - indistinguivel de uma
    # query lenta, medido em teste.
    target_pool_timeout_segundos: int = 5

    # ---------------------------------------------------------------
    # Groq - dormant. Migrado para OpenRouter por problemas de
    # formatacao de tool calls; campos mantidos sem uso em src/llm.py
    # para facilitar reverter se necessario.
    # ---------------------------------------------------------------
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_temperature: float = 0.0
    # Teto de tokens de saida por chamada. Contas on-demand da Groq tem
    # limite de output tokens por minuto (OTPM); sem este teto, uma
    # resposta longa do modelo pode sozinha estourar o limite da conta.
    groq_max_tokens: int = 512

    # ---------------------------------------------------------------
    # OpenRouter
    # ---------------------------------------------------------------
    openrouter_api_key: str = ""
    openrouter_model: str = "cohere/north-mini-code:free"
    openrouter_temperature: float = 0.0
    openrouter_max_tokens: int = 512
    # Sem isso, uma chamada ao modelo (gratuito, sujeito a instabilidade
    # de capacidade compartilhada) pode travar sem prazo.
    openrouter_timeout_segundos: int = 60

    # ---------------------------------------------------------------
    # Langfuse (tracing). O SDK leria LANGFUSE_* sozinho do ambiente,
    # mas passar por aqui mantem config.py como unica fonte de verdade
    # e da como desligar o tracing sem apagar credencial.
    # ---------------------------------------------------------------
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = "https://us.cloud.langfuse.com"
    langfuse_tracing_enabled: bool = True

    # ---------------------------------------------------------------
    # Agente
    # ---------------------------------------------------------------
    max_iteracoes: int = 10
    max_tabelas_por_chamada: int = 8
    query_timeout_segundos: int = 20
    max_linhas_retorno: int = 500

    # ---------------------------------------------------------------
    # Log de SQL. Nunca ligado para bancos alvo: as queries vem do LLM
    # e poluem o stdout. O registro util fica na tabela logs.
    # ---------------------------------------------------------------
    sql_echo: bool = False

    # ---------------------------------------------------------------
    # Logging (console/stdout via `logging` padrao). Independente da
    # tabela `logs` (auditoria de negocio gravada por log_service).
    # ---------------------------------------------------------------
    log_level: str = "INFO"

    @field_validator("log_level")
    @classmethod
    def _validar_log_level(cls, valor: str) -> str:
        nivel = valor.strip().upper()
        permitidos = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if nivel not in permitidos:
            raise ValueError(f"log_level deve ser um de {sorted(permitidos)}")
        return nivel

    @field_validator("app_database_url")
    @classmethod
    def _validar_url_app(cls, valor: str) -> str:
        if not valor or not valor.strip():
            raise ValueError("APP_DATABASE_URL nao pode ser vazia")
        return _normalizar_url(valor)

    @field_validator("ambiente")
    @classmethod
    def _validar_ambiente(cls, valor: str) -> str:
        permitidos = {"desenvolvimento", "homologacao", "producao"}
        if valor not in permitidos:
            raise ValueError(f"ambiente deve ser um de {sorted(permitidos)}")
        return valor

    # ---------------------------------------------------------------
    @property
    def em_producao(self) -> bool:
        return self.ambiente == "producao"

    @property
    def statement_timeout_ms(self) -> int:
        return self.query_timeout_segundos * 1000

    @property
    def langfuse_configurado(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)

    @property
    def timeout_cliente_segundos(self) -> int:
        """Teto imposto pelo cliente, acima do orcamento do servidor.

        Com o servidor alcancavel quem corta e o statement_timeout, que
        devolve 57014 e uma mensagem que o agente consegue usar. Este
        teto cobre o caso em que resposta nenhuma volta - espera no pool,
        pre_ping em socket morto, rede que sumiu.
        """
        return self.query_timeout_segundos + 2

    def url_do_banco_alvo(self, chave_conexao: str) -> str:
        """Resolve bancos.chave_conexao para a URL de conexao real.

        A chave vem do banco da aplicacao, nao de codigo. Por isso o
        formato e validado antes de tocar no ambiente: sem essa trava,
        um registro apontando para GROQ_API_KEY vazaria o segredo para
        dentro de uma string de conexao.
        """
        if not FORMATO_CHAVE_CONEXAO.match(chave_conexao or ""):
            raise ConfiguracaoInvalida(
                f"chave_conexao invalida: {chave_conexao!r}. "
                f"Deve casar com {PREFIXO_BANCO_ALVO}[A-Z0-9_]+"
            )

        url = os.getenv(chave_conexao)
        if not url:
            disponiveis = sorted(
                nome for nome in os.environ if nome.startswith(PREFIXO_BANCO_ALVO)
            )
            raise ConfiguracaoInvalida(
                f"Variavel de ambiente {chave_conexao} nao definida. "
                f"Disponiveis: {disponiveis or 'nenhuma'}"
            )

        return _normalizar_url(url)

    def bancos_alvo_disponiveis(self) -> list[str]:
        """Lista as chaves de banco alvo presentes no ambiente."""
        return sorted(
            nome
            for nome in os.environ
            if FORMATO_CHAVE_CONEXAO.match(nome) and os.environ[nome].strip()
        )


@lru_cache(maxsize=1)
def obter_configuracao() -> Configuracao:
    """Instancia unica, cacheada. Falha na subida se algo estiver errado."""
    try:
        return Configuracao()
    except Exception as erro:
        raise ConfiguracaoInvalida(
            f"Falha ao carregar configuracao: {erro}"
        ) from erro


configuracao = obter_configuracao()