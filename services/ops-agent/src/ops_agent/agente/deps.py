"""Dependencias injetadas no agente via RunContext."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from ops_agent.agente.prompts.sistema import PROMPT_SISTEMA_PADRAO
from ops_agent.config import obter_configuracao
from ops_agent.database import sessao_leitura


@dataclass
class DependenciasAgente:
    """Estado de UMA execucao do agente; nunca reaproveitar entre requisicoes."""

    usuario: str
    # Data no fuso do negocio: resolve "ate o fim do mes" e o inicio padrao do cupom.
    hoje: date
    max_fornecedores: int
    # Fabrica, nao sessao: cada tool abre e fecha a sua, porque entre duas
    # tool calls o LLM pode levar segundos e a transacao ficaria ociosa.
    abrir_sessao: Callable[[], AbstractAsyncContextManager[AsyncSession]] = sessao_leitura
    # Texto do system prompt desta execucao: buscado uma vez no Langfuse e
    # fixo para todas as chamadas ao LLM do run.
    prompt_sistema: str = PROMPT_SISTEMA_PADRAO
    # IDs devolvidos por tools nesta execucao. O validador de saida recusa
    # qualquer ID da proposta fora destes conjuntos (defesa contra ID alucinado).
    categorias_vistas: set[int] = field(default_factory=set)
    fornecedores_vistos: set[int] = field(default_factory=set)


def criar_dependencias(
    usuario: str, prompt_sistema: str = PROMPT_SISTEMA_PADRAO
) -> DependenciasAgente:
    configuracao = obter_configuracao()
    return DependenciasAgente(
        usuario=usuario,
        hoje=configuracao.hoje(),
        max_fornecedores=configuracao.ops_max_fornecedores_busca,
        prompt_sistema=prompt_sistema,
    )
