"""Execucao segura de SQL gerado pelo LLM.

O registry entrega uma conexao. Este modulo e o unico ponto onde uma
string vinda do modelo vira query executada, concentrando as travas que
o Postgres sozinho nao cobre.

Nao levanta excecao em erro de SQL: devolve a mensagem como texto para
o agente ler na proxima iteracao e corrigir sozinho.
"""

import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturoExpirou
from dataclasses import dataclass, field
from datetime import date, datetime, time as hora, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.exc import TimeoutError as PoolEsgotado

from src.config import configuracao
from src.database.registry import conexao_leitura, pid_do_backend
from src.log_stdout import truncar_texto

logger = logging.getLogger(__name__)

# Erro do Postgres para query cortada pelo statement_timeout. Vira texto
# para o agente, nao excecao: ele consegue agir nisso escrevendo uma
# query mais barata.
SQLSTATE_QUERY_CANCELADA = "57014"

# A execucao roda numa thread propria para que o teto de tempo cubra o
# caminho inteiro - espera por vaga no pool, pre_ping, execucao e fetch -
# e nao so a query, unica parte que o statement_timeout do servidor
# alcanca. Ao estourar o teto, a conexao crua e cancelada via
# cancel_safe() do psycopg, que e seguro chamar de outra thread: a thread
# presa morre em ~2s e devolve a vaga. Abandonar a thread como em
# src/llm.py nao serve aqui - o pool tem 5 vagas, e cada timeout
# queimaria uma delas.
_executor_consultas = ThreadPoolExecutor(thread_name_prefix="consulta_alvo")

# Comandos que nunca devem passar. O usuario read-only ja barra no banco,
# mas rejeitar antes evita round-trip e devolve mensagem mais clara.
COMANDOS_PROIBIDOS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE|"
    r"COPY|VACUUM|REINDEX|CALL|DO|SET|RESET)\b",
    re.IGNORECASE,
)

INICIO_VALIDO = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)

# Comentarios sao removidos antes da validacao: '--' e '/* */' sao a
# forma mais simples de esconder um comando proibido do regex.
COMENTARIO_LINHA = re.compile(r"--[^\n]*")
COMENTARIO_BLOCO = re.compile(r"/\*.*?\*/", re.DOTALL)

# Literais e identificadores citados tambem saem antes da analise, senao
# uma consulta legitima como WHERE mensagem LIKE '%DELETE%' seria
# rejeitada. A aspa simples escapada no Postgres e '', tratada aqui.
LITERAL_TEXTO = re.compile(r"'(?:[^']|'')*'")
IDENTIFICADOR_CITADO = re.compile(r'"(?:[^"]|"")*"')


class SQLRejeitado(ValueError):
    """SQL barrado pela validacao, antes de chegar ao banco."""


class FalhaDeInfraestrutura(RuntimeError):
    """Falha que o agente nao corrige reescrevendo a query.

    Excecao, e nao texto como os erros de SQL (regra 5 do CLAUDE.md):
    reenviar a mesma query com o pool esgotado ou a conexao morta so
    gasta iteracao e esconde o problema real de quem opera.
    """


class TempoDeQueryEsgotado(FalhaDeInfraestrutura):
    """Nada voltou do servidor dentro do teto do cliente."""


class FalhaDeConexao(FalhaDeInfraestrutura):
    """Pool esgotado, conexao morta ou falha do driver."""


@dataclass
class ResultadoConsulta:
    """Retorno da execucao, em formato pronto para virar texto ao LLM."""

    sucesso: bool
    colunas: list[str] = field(default_factory=list)
    linhas: list[dict[str, Any]] = field(default_factory=list)
    total_linhas: int = 0
    truncado: bool = False
    erro: str | None = None
    duracao_ms: int = 0
    sql: str = ""


def _limpar_para_analise(sql: str) -> str:
    """Remove comentarios e literais, deixando so a estrutura da query.

    Comentarios saem primeiro: sao a forma mais simples de esconder um
    comando do regex. Depois saem os literais, para que uma palavra
    proibida dentro de uma string nao gere falso positivo.

    Aspas desbalanceadas resultam em SQL que o Postgres rejeita na
    execucao, nunca em comando escondido passando pela validacao.
    """
    limpo = COMENTARIO_BLOCO.sub(" ", sql)
    limpo = COMENTARIO_LINHA.sub(" ", limpo)
    limpo = LITERAL_TEXTO.sub(" 'txt' ", limpo)
    limpo = IDENTIFICADOR_CITADO.sub(" ident ", limpo)
    return limpo


def validar_sql(sql: str) -> str:
    """Valida e normaliza o SQL. Levanta SQLRejeitado se nao passar.

    Devolve o SQL sem o ponto e virgula final, pronto para execucao.
    """
    if not sql or not sql.strip():
        raise SQLRejeitado("SQL vazio")

    limpo = sql.strip()

    # Modelos costumam devolver a query cercada por markdown.
    if limpo.startswith("```"):
        limpo = re.sub(r"^```(?:sql)?\s*", "", limpo)
        limpo = re.sub(r"\s*```$", "", limpo).strip()

    sem_ponto_virgula = limpo.rstrip().rstrip(";").rstrip()
    if not sem_ponto_virgula:
        raise SQLRejeitado("SQL vazio")

    analise = _limpar_para_analise(sem_ponto_virgula)

    # O SQLAlchemy executa 'SELECT 1; DROP TABLE x' como uma chamada so
    # e devolve apenas o ultimo resultado, silenciosamente.
    if ";" in analise:
        raise SQLRejeitado(
            "Multiplos comandos em uma unica query. Envie apenas um SELECT."
        )

    if not INICIO_VALIDO.match(analise):
        raise SQLRejeitado("Apenas consultas SELECT ou WITH sao permitidas.")

    proibido = COMANDOS_PROIBIDOS.search(analise)
    if proibido:
        raise SQLRejeitado(
            f"Comando '{proibido.group(1).upper()}' nao permitido. "
            f"Este agente tem acesso somente de leitura."
        )

    return sem_ponto_virgula


def _serializar(valor: Any) -> Any:
    """Converte tipos do Postgres para algo representavel como texto.

    Decimal vira float por legibilidade: o agente vai formatar o numero
    numa resposta em linguagem natural, nao fazer contabilidade com ele.
    """
    if valor is None or isinstance(valor, (str, int, float, bool)):
        return valor
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, (datetime, date, hora)):
        return valor.isoformat()
    if isinstance(valor, timedelta):
        return str(valor)
    if isinstance(valor, UUID):
        return str(valor)
    if isinstance(valor, (bytes, memoryview)):
        return f"<binario {len(bytes(valor))} bytes>"
    if isinstance(valor, (list, tuple)):
        return [_serializar(item) for item in valor]
    if isinstance(valor, dict):
        return {chave: _serializar(item) for chave, item in valor.items()}
    return str(valor)


def _consultar(
    chave_conexao: str,
    sql: str,
    limite: int,
    conexao_crua: dict[str, Any],
) -> tuple[list[str], list[dict[str, Any]], bool]:
    """Abre a conexao, executa e le o resultado. Roda na thread do pool.

    Publica a conexao psycopg em conexao_crua assim que a tem em maos,
    para que a thread principal possa cancelar a query se o teto de
    tempo estourar.
    """
    with conexao_leitura(chave_conexao) as conexao:
        crua = conexao.connection.dbapi_connection
        conexao_crua["conexao"] = crua
        logger.info(
            "Query iniciada em %s (pid=%s): %s",
            chave_conexao, pid_do_backend(crua), truncar_texto(sql),
        )
        cursor = conexao.execute(text(sql))

        if cursor.returns_rows:
            colunas = list(cursor.keys())
            # Busca uma linha a mais para saber se houve corte, sem
            # precisar carregar o resultado inteiro na memoria.
            brutas = cursor.fetchmany(limite + 1)
            truncado = len(brutas) > limite
            brutas = brutas[:limite]
            linhas = [
                {coluna: _serializar(valor) for coluna, valor in zip(colunas, linha)}
                for linha in brutas
            ]
        else:
            colunas, linhas, truncado = [], [], False

    return colunas, linhas, truncado


def _cancelar_query(conexao_crua: dict[str, Any], chave_conexao: str) -> None:
    """Cancela a query travada para a thread presa liberar a vaga no pool."""
    conexao = conexao_crua.get("conexao")
    if conexao is None:
        logger.warning(
            "Teto de tempo estourou em %s antes de haver conexao - "
            "espera por vaga no pool, nao query lenta",
            chave_conexao,
        )
        return
    try:
        conexao.cancel_safe(timeout=5.0)
        logger.warning("Query cancelada em %s por estourar o teto do cliente", chave_conexao)
    except Exception as erro:
        logger.error("Falha ao cancelar query em %s: %s", chave_conexao, erro)


def executar_consulta(
    chave_conexao: str,
    sql: str,
    max_linhas: int | None = None,
) -> ResultadoConsulta:
    """Executa SQL de leitura e devolve o resultado ja serializado.

    Erro de SQL vira ResultadoConsulta com sucesso=False, nunca excecao:
    o agente precisa ler a mensagem para corrigir a query (regra 5 do
    CLAUDE.md). Falha de infraestrutura - pool esgotado, conexao morta,
    nada voltando dentro do teto - levanta FalhaDeInfraestrutura, porque
    reescrever a query nao resolve nenhuma delas.
    """
    limite = max_linhas or configuracao.max_linhas_retorno
    inicio = time.perf_counter()

    try:
        sql_validado = validar_sql(sql)
    except SQLRejeitado as erro:
        return ResultadoConsulta(
            sucesso=False,
            erro=str(erro),
            sql=sql,
            duracao_ms=int((time.perf_counter() - inicio) * 1000),
        )

    conexao_crua: dict[str, Any] = {}
    futuro = _executor_consultas.submit(
        _consultar, chave_conexao, sql_validado, limite, conexao_crua
    )

    try:
        colunas, linhas, truncado = futuro.result(
            timeout=configuracao.timeout_cliente_segundos
        )

        duracao = int((time.perf_counter() - inicio) * 1000)
        logger.info(
            "Query concluida em %s: %d linhas, %dms, truncado=%s",
            chave_conexao, len(linhas), duracao, truncado,
        )
        return ResultadoConsulta(
            sucesso=True,
            colunas=colunas,
            linhas=linhas,
            total_linhas=len(linhas),
            truncado=truncado,
            duracao_ms=duracao,
            sql=sql_validado,
        )

    except FuturoExpirou:
        _cancelar_query(conexao_crua, chave_conexao)
        raise TempoDeQueryEsgotado(
            f"A consulta nao respondeu em {configuracao.timeout_cliente_segundos}s "
            f"e foi cancelada."
        ) from None

    except PoolEsgotado as erro:
        logger.error(
            "Pool de %s esgotado (teto de %d conexoes) apos %ds de espera",
            chave_conexao,
            configuracao.target_pool_size + configuracao.target_pool_max_overflow,
            configuracao.target_pool_timeout_segundos,
        )
        raise FalhaDeConexao(
            f"Sem conexao disponivel para {chave_conexao}: o pool esta no teto de "
            f"{configuracao.target_pool_size + configuracao.target_pool_max_overflow} "
            f"conexoes. Alguma consulta anterior nao liberou a vaga."
        ) from erro

    except SQLAlchemyError as erro:
        duracao = int((time.perf_counter() - inicio) * 1000)
        original = getattr(erro, "orig", None)
        sqlstate = getattr(original, "sqlstate", None)
        mensagem = (str(original) if original else str(erro)).strip()

        # Resposta do servidor sempre traz sqlstate; falha de conexao,
        # nunca. E o unico jeito confiavel de separar "o agente pode
        # corrigir isso" de "nao ha o que o agente faca".
        if sqlstate is None:
            logger.error("Conexao com %s falhou: %s", chave_conexao, mensagem)
            raise FalhaDeConexao(f"Falha de conexao com {chave_conexao}: {mensagem}") from erro

        if sqlstate == SQLSTATE_QUERY_CANCELADA:
            mensagem = (
                f"A consulta passou do limite de {configuracao.query_timeout_segundos}s "
                f"no servidor e foi cancelada. Reescreva de forma mais barata: "
                f"filtre mais, agregue no banco ou reduza o intervalo consultado."
            )

        logger.warning(
            "Consulta em %s rejeitada pelo banco (sqlstate=%s): %s",
            chave_conexao, sqlstate, mensagem,
        )
        return ResultadoConsulta(
            sucesso=False,
            erro=mensagem,
            duracao_ms=duracao,
            sql=sql_validado,
        )