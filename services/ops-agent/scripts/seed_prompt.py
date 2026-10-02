"""Publica a versao inicial do system prompt do ops-agent no Langfuse.

Uso (a partir de services/ops-agent):
    uv run --package ops-agent python scripts/seed_prompt.py

Deixa um projeto Langfuse novo pronto a partir de PROMPT_SISTEMA_PADRAO.
Se o prompt ja existir, nao publica nada: a partir da primeira versao, o
lugar de editar o prompt e a interface do Langfuse, nao o codigo. Use
--forcar para publicar uma nova versao a partir do texto do codigo (move o
label de producao para ela).
"""

import argparse
import logging

from langfuse.api import NotFoundError

from ops_agent.agente.prompts.sistema import (
    LABEL_PRODUCAO,
    NOME_PROMPT_SISTEMA,
    PROMPT_SISTEMA_PADRAO,
)
from ops_agent.config import obter_configuracao
from ops_agent.observabilidade.setup import obter_cliente


def seed(forcar: bool) -> None:
    logging.basicConfig(level=obter_configuracao().log_level)

    cliente = obter_cliente()
    if cliente is None:
        raise SystemExit(
            "Langfuse sem credenciais configuradas. Preencha LANGFUSE_PUBLIC_KEY "
            "e LANGFUSE_SECRET_KEY no .env antes de publicar o prompt."
        )

    if not forcar:
        # Sem fallback de proposito: "nao existe" precisa virar excecao, e
        # qualquer outro erro (credencial, rede) aborta em vez de publicar.
        try:
            existente = cliente.get_prompt(
                NOME_PROMPT_SISTEMA, label=LABEL_PRODUCAO, cache_ttl_seconds=0
            )
        except NotFoundError:
            existente = None
        if existente is not None:
            print(
                f"Prompt {NOME_PROMPT_SISTEMA!r} ja existe (v{existente.version} em "
                f"{LABEL_PRODUCAO}). Nada publicado; use --forcar para nova versao."
            )
            return

    prompt = cliente.create_prompt(
        name=NOME_PROMPT_SISTEMA,
        prompt=PROMPT_SISTEMA_PADRAO,
        labels=[LABEL_PRODUCAO],
        type="text",
        commit_message="Versao publicada por scripts/seed_prompt.py",
    )
    cliente.flush()
    print(f"Prompt {prompt.name!r} v{prompt.version} publicado (labels={prompt.labels}).")


if __name__ == "__main__":
    argumentos = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    argumentos.add_argument("--forcar", action="store_true", help="publica nova versao mesmo se existir")
    seed(argumentos.parse_args().forcar)
