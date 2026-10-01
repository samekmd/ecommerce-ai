"""Roda o dataset de regressao contra o agente e grava o run no Langfuse.

Uso (a partir de services/ops-agent):
    PYTHONPATH=. uv run --package ops-agent python scripts/rodar_experimento.py --nome "prompt v2"
    PYTHONPATH=. uv run --package ops-agent python scripts/rodar_experimento.py \
        --itens v0-produto-completo,v0-cupom-data-relativa

Cada execucao cria um run comparavel na interface do Langfuse: mova o
label `production` do prompt, rode de novo, e o Langfuse mostra item a
item o que melhorou e o que piorou. Por isso nao e uma suite de assert.

Avaliadores deterministicos, sem juiz LLM (razoes 0-1, 1 e o melhor caso):

1. tipo_correto - a output tool escolhida (produto, cupom, esclarecimento...)
   e a esperada.
2. campos_corretos - fracao das regras de campo do expected que passaram
   (a mini-DSL esta documentada em scripts/seed_dataset.py). Categoria e
   fornecedor sao resolvidos por nome no banco AGORA, nao no seed.
3. avisos_coerentes - so em itens que exigem aviso: a lista nao e vazia.
4. motivo_correto - so em esclarecimento: motivo entre os aceitos.
5. cadastravel - so em itens com a frase completa: a proposta passa no
   XCadastro, ou seja, o formulario aceitaria sem o usuario editar nada.

O que NAO e coberto: o texto dos avisos e da mensagem de esclarecimento
(se explicam bem o problema). Isso exigiria juiz LLM e segue humano.

Sequencial (max_concurrency=1): o Groq refaz 429 sozinho com esperas de
dezenas de segundos, e paralelismo so transformaria isso em timeout.
"""

import argparse
import asyncio
import logging
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from langfuse import Evaluation
from pydantic import BaseModel, ValidationError
from sqlalchemy import select

from ops_agent.agente import agente
from ops_agent.agente.prompts.sistema import obter_prompt_sistema
from ops_agent.config import obter_configuracao
from ops_agent.database import sessao_leitura
from ops_agent.models import Categoria, Fornecedor
from ops_agent.observabilidade.setup import instrumentar_agente, obter_cliente
from ops_agent.observabilidade.tracing import rastrear_interpretacao
from ops_agent.schemas.categoria import CategoriaCadastro
from ops_agent.schemas.cupom import CupomCadastro
from ops_agent.schemas.fornecedor import FornecedorCadastro
from ops_agent.schemas.interpretacao import tipo_da_interpretacao
from ops_agent.services.auditoria import categoria_do_erro
from scripts.seed_dataset import NOME_DATASET

logger = logging.getLogger(__name__)

NOME_EXPERIMENTO = "regressao-ops-agent"
USUARIO_EVAL = "eval-regressao"

# Produto fica de fora: SKU e imagem nunca vem da frase, entao nenhuma
# proposta de produto e cadastravel sem edicao, por desenho.
CADASTROS: dict[str, type[BaseModel]] = {
    "fornecedor": FornecedorCadastro,
    "categoria": CategoriaCadastro,
    "cupom": CupomCadastro,
}

_NUMERO = re.compile(r"^-?\d+(?:\.\d+)?$")


# ---------------------------------------------------------------------
# comparacao de valores
# ---------------------------------------------------------------------


def _como_decimal(valor: Any) -> Decimal | None:
    """Numero de qualquer origem; o dump JSON serializa Decimal como string."""
    if isinstance(valor, bool) or valor is None:
        return None
    if isinstance(valor, (int, float, Decimal)) or (
        isinstance(valor, str) and _NUMERO.match(valor)
    ):
        try:
            return Decimal(str(valor))
        except InvalidOperation:
            return None
    return None


def _sem_acento(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c)).casefold()


def _iguais(obtido: Any, esperado: Any) -> bool:
    # "10" e 10.00 sao o mesmo percentual; "BLACK10" nao e numero.
    numero_esperado, numero_obtido = _como_decimal(esperado), _como_decimal(obtido)
    if numero_esperado is not None and numero_obtido is not None:
        return numero_obtido == numero_esperado
    return obtido == esperado


async def _id_categoria(nome: str | None) -> int | None:
    if nome is None:
        return None
    async with sessao_leitura() as sessao:
        return await sessao.scalar(select(Categoria.id).where(Categoria.nome == nome))


async def _id_fornecedor(nome: str) -> int | None:
    # So ativo: o agente nao pode vincular produto a fornecedor inativo.
    async with sessao_leitura() as sessao:
        return await sessao.scalar(
            select(Fornecedor.id).where(Fornecedor.nome == nome, Fornecedor.ativo)
        )


async def conferir_regra(obtido: Any, regra: dict[str, Any]) -> tuple[bool, str]:
    """Aplica uma regra do expected; devolve (passou, o que se esperava)."""
    if "igual" in regra:
        return _iguais(obtido, regra["igual"]), f"igual a {regra['igual']!r}"
    if "em" in regra:
        return any(_iguais(obtido, v) for v in regra["em"]), f"um de {regra['em']!r}"
    if "nulo" in regra:
        return obtido is None, "vazio"
    if "contem" in regra:
        passou = isinstance(obtido, str) and _sem_acento(regra["contem"]) in _sem_acento(obtido)
        return passou, f"contendo {regra['contem']!r}"
    if "diferente" in regra:
        return not _iguais(obtido, regra["diferente"]), f"diferente de {regra['diferente']!r}"
    if "digitos" in regra:
        passou = isinstance(obtido, str) and re.sub(r"\D", "", obtido) == regra["digitos"]
        return passou, f"com os digitos {regra['digitos']}"
    if "categoria" in regra:
        esperado = await _id_categoria(regra["categoria"])
        return obtido == esperado, f"id {esperado} ({regra['categoria']})"
    if "categoria_em" in regra:
        ids = {nome: await _id_categoria(nome) for nome in regra["categoria_em"]}
        return obtido in ids.values(), f"um de {ids}"
    if "fornecedor" in regra:
        esperado = await _id_fornecedor(regra["fornecedor"])
        return obtido == esperado, f"id {esperado} ({regra['fornecedor']})"
    raise ValueError(f"Regra desconhecida no dataset: {regra!r}")


# ---------------------------------------------------------------------
# task: uma frase do dataset pelo agente
# ---------------------------------------------------------------------


async def interpretar(*, item: Any, **_kwargs: Any) -> dict[str, Any]:
    """Roda o agente como o POST /interpretar, sem a auditoria.

    Mesmo caminho da rota (prompt do Langfuse + trace ligado a versao),
    com a data do item injetada. Falha vira categoria no output, nunca
    a mensagem, e nao derruba o run.
    """
    entrada = item.input or {}
    # SDK sincrono: num cache miss faria I/O de rede dentro do event loop.
    prompt = await asyncio.to_thread(obter_prompt_sistema)
    try:
        async with rastrear_interpretacao(USUARIO_EVAL, entrada["mensagem"], prompt) as rastro:
            saida = await agente.interpretar(
                entrada["mensagem"],
                USUARIO_EVAL,
                prompt.texto,
                hoje=date.fromisoformat(entrada["hoje"]),
            )
            rastro.registrar_saida(saida)
    except Exception as erro:  # noqa: BLE001 - um item nao derruba o run; vira categoria
        categoria = categoria_do_erro(erro)
        logger.error("Item %s falhou: %s", item.id, categoria)
        return {"tipo": None, "proposta": None, "falha": categoria, "prompt_versao": prompt.versao}

    return {
        "tipo": tipo_da_interpretacao(saida),
        "proposta": saida.model_dump(mode="json"),
        "falha": None,
        "prompt_versao": prompt.versao,
    }


# ---------------------------------------------------------------------
# avaliadores
# ---------------------------------------------------------------------


def _nota(nome: str, passou: bool, comentario: str) -> Evaluation:
    return Evaluation(name=nome, value=1.0 if passou else 0.0, comment=comentario)


def tipo_correto(*, output: Any, expected_output: Any, **_kwargs: Any) -> Evaluation:
    if output.get("falha"):
        return _nota("tipo_correto", False, f"Sem proposta: {output['falha']}")
    esperado, obtido = expected_output["tipo"], output["tipo"]
    return _nota("tipo_correto", obtido == esperado, f"Esperado {esperado}, veio {obtido}.")


async def campos_corretos(
    *, output: Any, expected_output: Any, **_kwargs: Any
) -> Evaluation | list[Any]:
    regras: dict[str, dict[str, Any]] = expected_output.get("campos") or {}
    if not regras:
        return []  # esclarecimento: nao ha campo a conferir
    if output.get("tipo") != expected_output["tipo"]:
        # Conta como zero em vez de sumir: sem isso a media por entidade
        # melhoraria justamente quando o agente erra o tipo.
        return _nota("campos_corretos", False, f"Tipo errado ({output.get('tipo')}).")

    proposta = output["proposta"]
    falhas = []
    for campo, regra in regras.items():
        obtido = proposta.get(campo)
        passou, esperado = await conferir_regra(obtido, regra)
        if not passou:
            falhas.append(f"{campo}: esperado {esperado}, veio {obtido!r}")

    passaram = len(regras) - len(falhas)
    return Evaluation(
        name="campos_corretos",
        value=passaram / len(regras),
        comment="; ".join(falhas) or f"{passaram}/{len(regras)} campos ok.",
        metadata={"campos_com_falha": [f.split(":")[0] for f in falhas]},
    )


def avisos_coerentes(
    *, output: Any, expected_output: Any, **_kwargs: Any
) -> Evaluation | list[Any]:
    if expected_output.get("avisos") != "obrigatorio" or output.get("tipo") != expected_output["tipo"]:
        return []
    avisos = (output["proposta"] or {}).get("avisos") or []
    return _nota("avisos_coerentes", bool(avisos), f"{len(avisos)} aviso(s): {avisos}")


def motivo_correto(
    *, output: Any, expected_output: Any, **_kwargs: Any
) -> Evaluation | list[Any]:
    aceitos = expected_output.get("motivos")
    if not aceitos or output.get("tipo") != "esclarecimento":
        return []  # tipo errado ja aparece em tipo_correto
    motivo = output["proposta"].get("motivo")
    return _nota("motivo_correto", motivo in aceitos, f"Aceitos {aceitos}, veio {motivo!r}.")


def cadastravel(*, output: Any, expected_output: Any, **_kwargs: Any) -> Evaluation | list[Any]:
    tipo = expected_output["tipo"]
    if not expected_output.get("cadastravel") or output.get("tipo") != tipo:
        return []
    payload = {k: v for k, v in output["proposta"].items() if k != "avisos"}
    try:
        CADASTROS[tipo].model_validate(payload)
    except ValidationError as erro:
        # So o nome do campo: o valor do erro nao acrescenta e poderia ser grande.
        campos = sorted({".".join(str(p) for p in e["loc"]) or "__root__" for e in erro.errors()})
        return _nota("cadastravel", False, f"Formulario recusaria: {campos}")
    return _nota("cadastravel", True, "Proposta aceita pelo formulario sem edicao.")


# ---------------------------------------------------------------------
# agregados do run
# ---------------------------------------------------------------------


def _media(valores: list[float]) -> float | None:
    return sum(valores) / len(valores) if valores else None


def medias_por_avaliador(*, item_results: Any, **_kwargs: Any) -> list[Evaluation]:
    por_nome: dict[str, list[float]] = {}
    for resultado in item_results:
        for avaliacao in resultado.evaluations:
            if isinstance(avaliacao.value, (int, float)):
                por_nome.setdefault(avaliacao.name, []).append(float(avaliacao.value))
    return [
        Evaluation(name=f"media_{nome}", value=media, comment=f"{len(valores)} item(ns)")
        for nome, valores in sorted(por_nome.items())
        if (media := _media(valores)) is not None
    ]


def acerto_por_entidade(*, item_results: Any, **_kwargs: Any) -> list[Evaluation]:
    """Media de todas as notas dos itens de cada entidade.

    Separa "piorou em cupom" de "piorou em produto", que a media geral esconde.
    """
    por_entidade: dict[str, list[float]] = {}
    for resultado in item_results:
        metadata = (resultado.item.metadata or {}) if resultado.item else {}
        entidade = metadata.get("entidade", "sem_entidade")
        for avaliacao in resultado.evaluations:
            if isinstance(avaliacao.value, (int, float)):
                por_entidade.setdefault(entidade, []).append(float(avaliacao.value))
    return [
        Evaluation(name=f"acerto_{entidade}", value=media, comment=f"{len(valores)} nota(s)")
        for entidade, valores in sorted(por_entidade.items())
        if (media := _media(valores)) is not None
    ]


# ---------------------------------------------------------------------


def _argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--nome", help="Nome do run no Langfuse. Default: data/hora + modelos.")
    parser.add_argument(
        "--itens", help="Ids separados por virgula, para rodar um subconjunto e poupar cota."
    )
    return parser.parse_args()


def main() -> None:
    configuracao = obter_configuracao()
    logging.basicConfig(level=configuracao.log_level)
    argumentos = _argumentos()

    cliente = obter_cliente()
    if cliente is None:
        raise SystemExit(
            "Langfuse sem credenciais configuradas. Preencha LANGFUSE_PUBLIC_KEY e "
            "LANGFUSE_SECRET_KEY no .env antes de rodar o experimento."
        )
    instrumentar_agente()

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

    modelos = configuracao.modelos_em_uso
    run_name = argumentos.nome or f"{datetime.now(configuracao.fuso):%Y-%m-%d %H:%M} - {modelos}"
    print(f"Rodando {len(itens)} item(ns) como run {run_name!r}...")

    resultado = cliente.run_experiment(
        name=NOME_EXPERIMENTO,
        run_name=run_name,
        description=f"Regressao do ops-agent, {len(itens)} de {len(dataset.items)} itens. {modelos}.",
        data=itens,
        task=interpretar,
        evaluators=[tipo_correto, campos_corretos, avisos_coerentes, motivo_correto, cadastravel],
        run_evaluators=[medias_por_avaliador, acerto_por_entidade],
        max_concurrency=1,
        metadata={"modelos": modelos, "itens_rodados": ",".join(item.id for item in itens)},
    )

    cliente.flush()
    print(resultado.format())


if __name__ == "__main__":
    main()
