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
from dataclasses import dataclass, field
from datetime import date, datetime, time as hora, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.config import configuracao
from src.database.registry import conexao_leitura

logger = logging.getLogger(__name__)

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


def executar_consulta(
    chave_conexao: str,
    sql: str,
    max_linhas: int | None = None,
) -> ResultadoConsulta:
    """Executa SQL de leitura e devolve o resultado ja serializado.

    Erros de banco viram ResultadoConsulta com sucesso=False, nunca
    excecao: o agente precisa ler a mensagem para corrigir a query.
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

    try:
        with conexao_leitura(chave_conexao) as conexao:
            cursor = conexao.execute(text(sql_validado))

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

        duracao = int((time.perf_counter() - inicio) * 1000)
        return ResultadoConsulta(
            sucesso=True,
            colunas=colunas,
            linhas=linhas,
            total_linhas=len(linhas),
            truncado=truncado,
            duracao_ms=duracao,
            sql=sql_validado,
        )

    except SQLAlchemyError as erro:
        duracao = int((time.perf_counter() - inicio) * 1000)
        original = getattr(erro, "orig", None)
        mensagem = str(original) if original else str(erro)
        logger.warning("Falha ao executar consulta em %s: %s", chave_conexao, mensagem)
        return ResultadoConsulta(
            sucesso=False,
            erro=mensagem.strip(),
            duracao_ms=duracao,
            sql=sql_validado,
        )