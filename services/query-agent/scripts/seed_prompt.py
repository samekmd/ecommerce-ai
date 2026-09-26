"""Publica a versao inicial do prompt de sistema do agente no Langfuse.

Uso: `PYTHONPATH=. uv run python scripts/seed_prompt.py`

Serve para deixar um ambiente novo (ou um projeto Langfuse novo) pronto
a partir do texto em src/prompts.py. Rodar de novo nao duplica nada, mas
cria outra versao e move o label de producao para ela - a partir da
primeira publicacao, o lugar de editar o prompt e a interface do
Langfuse, nao este arquivo.
"""

from src.logging_config import configurar_logging
from src.observability.setup import obter_cliente
from src.prompts import LABEL_PRODUCAO, NOME_PROMPT_SISTEMA, PROMPT_SISTEMA_PADRAO


def seed() -> None:
    configurar_logging()

    cliente = obter_cliente()
    if cliente is None:
        raise SystemExit(
            "Langfuse sem credenciais configuradas. Preencha LANGFUSE_PUBLIC_KEY "
            "e LANGFUSE_SECRET_KEY no .env antes de publicar o prompt."
        )

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
    seed()
