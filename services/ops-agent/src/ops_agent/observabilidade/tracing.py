"""Trace de uma interpretacao: span raiz, usuario, tags e prompt ligado.

Todo erro de observabilidade e engolido aqui, e so aqui: e o unico ponto
do servico onde essa defesa se justifica. Excecoes da aplicacao dentro do
bloco atravessam normalmente.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any

from langfuse import propagate_attributes

from ops_agent.agente.prompts.sistema import PromptSistema
from ops_agent.config import obter_configuracao
from ops_agent.observabilidade.setup import obter_cliente
from ops_agent.schemas.interpretacao import Interpretacao, tipo_da_interpretacao

logger = logging.getLogger(__name__)

TAG_SERVICO = "ops-agent"
NOME_TRACE = "ops-interpretar"


class Rastro:
    """Alca do span raiz. Com observacao None, todos os metodos sao no-op."""

    def __init__(self, observacao: Any | None = None) -> None:
        self._observacao = observacao

    @property
    def trace_id(self) -> str | None:
        if self._observacao is None:
            return None
        try:
            return self._observacao.trace_id
        except Exception:
            logger.exception("Falha ao ler trace_id; auditoria segue sem ele.")
            return None

    def registrar_saida(self, saida: Interpretacao) -> None:
        self._atualizar(
            output=saida.model_dump(mode="json"),
            metadata={"tipo": tipo_da_interpretacao(saida)},
        )

    def registrar_erro(self, categoria: str) -> None:
        # Categoria, nunca a mensagem da excecao: ela pode carregar dado de
        # resposta do provider ou detalhe interno.
        self._atualizar(level="ERROR", status_message=categoria)

    def _atualizar(self, **campos: Any) -> None:
        if self._observacao is None:
            return
        try:
            self._observacao.update(**campos)
        except Exception:
            logger.exception("Falha ao atualizar o trace; seguindo sem isso.")


def tags_da_interpretacao() -> list[str]:
    return [TAG_SERVICO, f"modelo-{obter_configuracao().modelo_principal}"]


@asynccontextmanager
async def rastrear_interpretacao(
    usuario: str, mensagem: str, prompt: PromptSistema
) -> AsyncIterator[Rastro]:
    """Abre o span raiz e propaga usuario, tags e prompt aos spans do agente.

    O prompt so e propagado quando veio do Langfuse: ligar a generation ao
    texto embutido (fallback) atribuiria a metrica a uma versao que nao
    existe.
    """
    cliente = obter_cliente()
    if cliente is None:
        yield Rastro()
        return

    pilha = AsyncExitStack()
    try:
        observacao = pilha.enter_context(
            cliente.start_as_current_observation(
                name="interpretar", as_type="agent", input={"mensagem": mensagem}
            )
        )
        pilha.enter_context(
            propagate_attributes(
                user_id=usuario,
                trace_name=NOME_TRACE,
                tags=tags_da_interpretacao(),
                metadata={
                    # Cadeia configurada; o modelo que respondeu cada chamada
                    # aparece na propria generation.
                    "modelo": obter_configuracao().modelos_em_uso,
                    "prompt_versao": str(prompt.versao) if prompt.versao else "fallback",
                },
                prompt=prompt.cliente,
            )
        )
        rastro = Rastro(observacao)
    except Exception:
        logger.exception("Falha ao abrir o trace; seguindo sem observabilidade.")
        await _fechar_sem_propagar(pilha)
        yield Rastro()
        return

    async with pilha:
        yield rastro


async def _fechar_sem_propagar(pilha: AsyncExitStack) -> None:
    try:
        await pilha.aclose()
    except Exception:
        logger.exception("Falha ao fechar o trace parcialmente aberto.")
