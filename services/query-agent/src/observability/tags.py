"""Tags dos traces do Langfuse.

So entram tags conhecidas na abertura do trace: o CallbackHandler le
`langfuse_tags` apenas no span raiz (onde parent_run_id e None). Uma
classificacao descoberta depois - erro de SQL, falha de infra - nao tem
como virar tag; esse sinal vai como level="ERROR" e status_message no
span, via tracing.anotar_consulta.
"""

from src.config import configuracao

TAG_AGENTE = "agente-sql"


def tags_da_pergunta(banco_id: int) -> list[str]:
    return [
        TAG_AGENTE,
        f"banco-{banco_id}",
        f"modelo-{configuracao.openrouter_model}",
    ]
