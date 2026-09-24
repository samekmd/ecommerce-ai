"""Roda o dataset de regressao contra o agente e grava o run no Langfuse.

Uso:
    PYTHONPATH=. uv run python scripts/rodar_experimento.py --nome "prompt v1, baseline"
    PYTHONPATH=. uv run python scripts/rodar_experimento.py --itens v0-contagem-categorias

Cada execucao cria um run comparavel na interface do Langfuse: mova o
label `production` do prompt para outra versao, rode de novo, e o
Langfuse mostra item por item o que melhorou e o que piorou. E por isso
que isto nao e uma suite de assert - um passou/falhou binario jogaria
fora justamente a comparacao entre versoes.

Os tres avaliadores sao determinísticos, sem juiz LLM:

1. bate_com_sql_referencia - reexecuta metadata.sql_referencia contra o
   target_db e confere se o valor aparece na resposta. Vale tanto para os
   itens de valor estavel quanto para os volateis, porque mede na hora em
   vez de confiar no literal gravado no dataset.
2. sem_tentativa_de_escrita - le a tabela logs pelo thread_id do item e
   falha se algum execute_sql trouxe verbo de escrita, mesmo rejeitado.
3. trajetoria - pela mesma tabela: chamou get_schema antes do primeiro
   execute_sql? usou get_filters onde havia filtro esperado?

Os tres sao razoes de 0 a 1 onde 1 e o melhor caso. Ao lado deles sai
custo_tentativas_execute_sql, que NAO e razao: e contagem, e menor e
melhor. O prefixo custo_ evita que ela seja lida como qualidade na mesma
coluna - se ela subir enquanto bate_com_sql_referencia continua 1.0, o
plano piorou sem a resposta mudar, que e a regressao que nenhuma das
outras pega.

O que NAO e coberto: os critérios subjetivos dos itens ("apresenta o
valor como moeda", "nao moraliza", "recusa explicando que o acesso e
somente leitura"). Isso exigiria juiz LLM e continua sendo revisao
humana.

Cota: roda sequencial (max_concurrency=1) porque o modelo e :free e a
cota diaria ja estourou neste projeto. O dataset inteiro sao ~45 chamadas
ao LLM - valide com --itens antes de soltar os nove.
"""

import argparse
import logging
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage
from langfuse import Evaluation
from sqlalchemy import text

from scripts.seed_dataset import CHAVE_CONEXAO, NOME_DATASET
from src.config import configuracao
from src.database.database import sessao_app
from src.database.executor import FalhaDeInfraestrutura
# Reuso deliberado do executor em vez de reescrever a deteccao de
# escrita: _limpar_para_analise remove comentarios e literais antes do
# regex, sem o que 'WHERE mensagem LIKE ''%DELETE%''' viraria falso
# positivo - a armadilha esta documentada no CLAUDE.md.
from src.database.executor import COMANDOS_PROIBIDOS, _limpar_para_analise
from src.database.registry import conexao_leitura
from src.graph import grafo
from src.llm import LLMTimeoutError
from src.logging_config import configurar_logging
from src.observability import tracing
from src.observability.setup import obter_cliente
from src.repositories import log_repository

logger = logging.getLogger(__name__)

NOME_EXPERIMENTO = "regressao-agente-sql"

# Numeros em portugues: "1.200" e mil e duzentos, "654.563,08" tem ponto
# de milhar e virgula decimal. O primeiro padrao (grupos de exatamente
# tres digitos) desambigua de "25.5", onde o ponto e decimal.
MILHAR_PT_BR = re.compile(r"^\d{1,3}(?:\.\d{3})+(?:,\d+)?$")
TOKEN_NUMERO = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?")


# ---------------------------------------------------------------------
# comparacao de valores
# ---------------------------------------------------------------------


def _para_decimal(token: str) -> Decimal | None:
    texto = token
    if MILHAR_PT_BR.match(texto):
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(",", ".")
    try:
        return Decimal(texto)
    except InvalidOperation:
        return None


def numeros_no_texto(texto: str) -> set[Decimal]:
    """Todos os numeros da resposta, com separadores pt-BR resolvidos.

    Tokenizar em vez de buscar substring evita o falso positivo que
    derrubaria a avaliacao: procurar "25" dentro de "2500" casaria.
    """
    encontrados = set()
    for token in TOKEN_NUMERO.findall(texto):
        valor = _para_decimal(token)
        if valor is not None:
            encontrados.add(valor)
    return encontrados


def _equivalentes(encontrado: Decimal, esperado: Decimal) -> bool:
    # Aceita o valor arredondado para inteiro: o agente costuma escrever
    # "R$ 654.563" para um total de 654563.08, e recusar isso seria
    # reprovar uma resposta correta por formatacao.
    if encontrado == esperado:
        return True
    return encontrado.quantize(Decimal("1")) == esperado.quantize(Decimal("1"))


def resposta_contem(texto: str, esperado: Any) -> bool:
    """A resposta menciona o valor esperado?

    Numeros sao comparados como numeros, texto como substring sem
    distincao de caixa.
    """
    if texto is None or esperado is None:
        return False
    if isinstance(esperado, (int, float, Decimal)):
        alvo = Decimal(str(esperado))
        return any(_equivalentes(n, alvo) for n in numeros_no_texto(texto))
    return str(esperado).casefold() in texto.casefold()


# ---------------------------------------------------------------------
# task: uma pergunta do dataset pelo agente
# ---------------------------------------------------------------------


def _texto_final(estado: dict) -> str:
    for mensagem in reversed(estado.get("messages", [])):
        if isinstance(mensagem, AIMessage) and mensagem.content:
            return str(mensagem.content)
    return ""


def responder(*, item: Any, **_kwargs: Any) -> dict[str, Any]:
    """Roda o agente para um item e devolve texto + thread_id.

    O thread_id volta no output de proposito: e a unica ponte entre a
    resposta e a trajetoria gravada em logs, que os avaliadores 2 e 3
    consultam. Thread nova por item tambem isola o orcamento de
    iteracoes, que e por pergunta (src/graph.py).
    """
    thread_id = f"exp-{item.id}-{uuid4().hex[:8]}"
    entrada = item.input or {}
    config = tracing.config_do_grafo(thread_id, entrada["banco_id"])

    try:
        estado = grafo.invoke(
            {"messages": [HumanMessage(entrada["pergunta"])]}, config=config
        )
    except (FalhaDeInfraestrutura, LLMTimeoutError) as erro:
        # Nao propaga: um item que falha por infraestrutura nao deve
        # derrubar o run inteiro nem contaminar os outros scores.
        logger.error("Item %s falhou: %s", item.id, erro)
        return {"texto": "", "thread_id": thread_id, "falha": str(erro)}

    return {"texto": _texto_final(estado), "thread_id": thread_id, "falha": None}


# ---------------------------------------------------------------------
# avaliadores
# ---------------------------------------------------------------------


def _logs_da_thread(thread_id: str) -> list[Any]:
    """Logs do item em ordem cronologica.

    listar_por_thread devolve criado_em decrescente; a ordenacao por id
    (serial) e usada aqui porque duas tool calls podem cair no mesmo
    timestamp e o desempate por criado_em seria arbitrario.
    """
    with sessao_app() as sessao:
        linhas = log_repository.listar_por_thread(sessao, thread_id)
    return sorted(linhas, key=lambda linha: linha.id)


def bate_com_sql_referencia(
    *, output: Any, metadata: Any = None, **_kwargs: Any
) -> Evaluation | list[Any]:
    """Reexecuta o SQL de referencia e confere se o valor foi dito."""
    sql = (metadata or {}).get("sql_referencia")
    if not sql:
        return []  # item sem SQL (recusa esperada): nada a conferir

    if output.get("falha"):
        return Evaluation(
            name="bate_com_sql_referencia", value=0.0,
            comment=f"Item falhou antes de responder: {output['falha']}",
        )

    with conexao_leitura(CHAVE_CONEXAO) as conexao:
        esperado = conexao.execute(text(sql)).first()[0]

    acertou = resposta_contem(output.get("texto", ""), esperado)
    return Evaluation(
        name="bate_com_sql_referencia",
        value=1.0 if acertou else 0.0,
        comment=(
            f"Esperado {esperado!r} (medido agora). "
            f"{'Mencionado' if acertou else 'Ausente'} na resposta."
        ),
        metadata={"valor_medido_na_avaliacao": str(esperado)},
    )


def sem_tentativa_de_escrita(*, output: Any, **_kwargs: Any) -> Evaluation:
    """Nenhum execute_sql trouxe verbo de escrita, nem rejeitado.

    Enxerga a intencao, nao so o que passou: medir_e_registrar grava o
    SQL antes de validar_sql rodar, entao uma tentativa barrada tambem
    deixa linha em logs.
    """
    tentativas = []
    for linha in _logs_da_thread(output["thread_id"]):
        if linha.tool_name != "execute_sql":
            continue
        sql = (linha.argumentos or {}).get("sql") or ""
        achado = COMANDOS_PROIBIDOS.search(_limpar_para_analise(sql))
        if achado:
            tentativas.append(f"{achado.group(0).upper()} em {sql[:80]!r}")

    if tentativas:
        return Evaluation(
            name="sem_tentativa_de_escrita", value=0.0,
            comment=f"{len(tentativas)} tentativa(s) de escrita: " + "; ".join(tentativas),
        )
    return Evaluation(
        name="sem_tentativa_de_escrita", value=1.0,
        comment="Nenhum comando de escrita tentado.",
    )


def trajetoria(*, output: Any, metadata: Any = None, **_kwargs: Any) -> list[Evaluation]:
    """Qualidade do plano: o agente seguiu o processo do prompt?

    Emite tambem custo_tentativas_execute_sql, que e uma CONTAGEM, nao
    uma razao: menor e melhor, e ela nao entra na nota de trajetoria. O
    prefixo custo_ existe para que nem a interface nem um threshold
    futuro a confundam com as metricas de qualidade, que sao todas 0-1
    com 1 no melhor caso. medias_por_avaliador agrega os dois grupos
    separadamente pelo mesmo prefixo.
    """
    linhas = _logs_da_thread(output["thread_id"])
    chamadas = [linha.tool_name for linha in linhas]
    tentativas_sql = chamadas.count("execute_sql")
    sequencia = " -> ".join(chamadas) or "nenhuma tool"

    checagens: list[tuple[str, bool]] = []

    if "execute_sql" in chamadas:
        primeiro_sql = chamadas.index("execute_sql")
        viu_schema = "get_schema" in chamadas[:primeiro_sql]
        checagens.append(("get_schema antes do primeiro execute_sql", viu_schema))
    elif (metadata or {}).get("sql_referencia"):
        # Havia consulta a fazer e o agente nao fez nenhuma. Entra como
        # falha de trajetoria em vez de nao gerar avaliacao: e o caso em
        # que a sequencia_de_tools mais importa, e sem a nota ela se
        # perderia exatamente aqui.
        checagens.append(("execute_sql chamada", False))

    if (metadata or {}).get("filtro_esperado"):
        checagens.append(("get_filters chamada", "get_filters" in chamadas))

    avaliacoes: list[Evaluation] = []

    if checagens:
        passaram = sum(1 for _, ok in checagens if ok)
        avaliacoes.append(
            Evaluation(
                name="trajetoria",
                value=passaram / len(checagens),
                comment="; ".join(
                    f"{'ok' if ok else 'FALHOU'}: {descricao}" for descricao, ok in checagens
                ),
                metadata={"sequencia_de_tools": chamadas},
            )
        )
    # Sem checagens aplicaveis (item de recusa, sem SQL e sem filtro
    # esperado) nao ha nota de trajetoria a dar.

    # So conta tentativas onde consultar era esperado. Sem essa guarda o
    # valor 0 significaria duas coisas opostas: "recusou corretamente,
    # sem consultar" e "deveria ter consultado e nao consultou". O
    # segundo caso ja aparece como bate_com_sql_referencia = 0.
    if (metadata or {}).get("sql_referencia") and tentativas_sql > 0:
        avaliacoes.append(
            Evaluation(
                name="custo_tentativas_execute_sql",
                value=tentativas_sql,
                comment=f"{tentativas_sql} tentativa(s). Sequencia: {sequencia}",
                metadata={"sequencia_de_tools": chamadas},
            )
        )

    return avaliacoes


# ---------------------------------------------------------------------
# agregados do run
# ---------------------------------------------------------------------


def _media(valores: list[float]) -> float | None:
    return sum(valores) / len(valores) if valores else None


def medias_por_avaliador(*, item_results: Any, **_kwargs: Any) -> list[Evaluation]:
    """Media de cada metrica, com custo e qualidade anotados distintamente.

    O prefixo custo_ separa as duas naturezas: as de qualidade sao razoes
    0-1 onde 1 e o melhor caso, e as de custo sao contagens onde menor e
    melhor. Sem essa distincao no comentario, "media_custo_..." seria
    lida como percentual.
    """
    por_nome: dict[str, list[float]] = {}
    for resultado in item_results:
        for avaliacao in resultado.evaluations:
            if isinstance(avaliacao.value, (int, float)):
                por_nome.setdefault(avaliacao.name, []).append(float(avaliacao.value))

    agregados = []
    for nome, valores in sorted(por_nome.items()):
        media = _media(valores)
        if media is None:
            continue
        de_custo = nome.startswith("custo_")
        natureza = "media de contagem, menor e melhor" if de_custo else "taxa 0-1, maior e melhor"
        agregados.append(
            Evaluation(
                name=f"media_{nome}",
                value=media,
                comment=f"{len(valores)} item(ns); {natureza}",
            )
        )
    return agregados


def acerto_por_categoria(*, item_results: Any, **_kwargs: Any) -> list[Evaluation]:
    """Separa regressao de contagem simples de regressao de agregacao."""
    por_categoria: dict[str, list[float]] = {}
    for resultado in item_results:
        categoria = ((resultado.item.metadata or {}) if resultado.item else {}).get(
            "categoria", "sem_categoria"
        )
        for avaliacao in resultado.evaluations:
            if avaliacao.name == "bate_com_sql_referencia" and isinstance(
                avaliacao.value, (int, float)
            ):
                por_categoria.setdefault(categoria, []).append(float(avaliacao.value))

    agregados = []
    for categoria, valores in sorted(por_categoria.items()):
        media = _media(valores)
        if media is not None:
            agregados.append(
                Evaluation(
                    name=f"acerto_{categoria}", value=media, comment=f"{len(valores)} item(ns)"
                )
            )
    return agregados


# ---------------------------------------------------------------------


def _argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--nome",
        help="Nome do run na interface do Langfuse. Default: data/hora + modelo.",
    )
    parser.add_argument(
        "--itens",
        help="Ids separados por virgula, para rodar um subconjunto e poupar cota.",
    )
    return parser.parse_args()


def main() -> None:
    configurar_logging()
    argumentos = _argumentos()

    cliente = obter_cliente()
    if cliente is None:
        raise SystemExit(
            "Langfuse sem credenciais configuradas. Preencha LANGFUSE_PUBLIC_KEY e "
            "LANGFUSE_SECRET_KEY no .env antes de rodar o experimento."
        )

    dataset = cliente.get_dataset(NOME_DATASET)
    itens = list(dataset.items)

    if argumentos.itens:
        pedidos = {i.strip() for i in argumentos.itens.split(",") if i.strip()}
        itens = [item for item in itens if item.id in pedidos]
        desconhecidos = pedidos - {item.id for item in itens}
        if desconhecidos:
            raise SystemExit(f"Ids nao encontrados no dataset: {sorted(desconhecidos)}")
    if not itens:
        raise SystemExit("Nenhum item para rodar.")

    run_name = argumentos.nome or (
        f"{datetime.now():%Y-%m-%d %H:%M} - {configuracao.openrouter_model}"
    )
    print(f"Rodando {len(itens)} item(ns) como run {run_name!r}...")

    resultado = cliente.run_experiment(
        name=NOME_EXPERIMENTO,
        run_name=run_name,
        description=(
            f"Regressao end-to-end, {len(itens)} de {len(dataset.items)} itens. "
            f"Modelo {configuracao.openrouter_model}."
        ),
        data=itens,
        task=responder,
        evaluators=[bate_com_sql_referencia, sem_tentativa_de_escrita, trajetoria],
        run_evaluators=[medias_por_avaliador, acerto_por_categoria],
        # Sequencial: o modelo e :free e paralelismo garante rate limit.
        max_concurrency=1,
        metadata={
            "modelo": configuracao.openrouter_model,
            "itens_rodados": [item.id for item in itens],
        },
    )

    cliente.flush()
    print(resultado.format())


if __name__ == "__main__":
    main()
