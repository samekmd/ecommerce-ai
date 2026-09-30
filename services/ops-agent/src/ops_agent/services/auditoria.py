"""Auditoria no app_db: frase, proposta, payload confirmado e resultado.

A auditoria nunca derruba a requisicao. O cadastro ja foi commitado em
outro banco (nao ha transacao entre os dois), entao uma falha aqui vira
log de erro e o usuario recebe a resposta correta.
"""

import logging
import uuid
from typing import Any, Literal

from pydantic import BaseModel
from pydantic_ai.exceptions import (
    FallbackExceptionGroup,
    ModelAPIError,
    UnexpectedModelBehavior,
    UsageLimitExceeded,
)
from sqlalchemy.exc import DBAPIError, TimeoutError as TimeoutPool

from ops_agent.database import sessao_app
from ops_agent.repositories import auditoria as auditoria_repository
from ops_agent.schemas.interpretacao import Interpretacao, tipo_da_interpretacao
from ops_agent.schemas.produto import ProdutoCadastro

logger = logging.getLogger(__name__)

Entidade = Literal["produto", "fornecedor", "categoria", "cupom"]
Resultado = Literal["criado", "conflito", "invalido", "erro"]


def categoria_do_erro(erro: BaseException) -> str:
    """Categoria estavel para metrica; a mensagem da excecao nunca e gravada."""
    if isinstance(erro, UsageLimitExceeded):
        return "limite_requisicoes"
    if isinstance(erro, UnexpectedModelBehavior):
        return "retries_esgotados"
    if isinstance(erro, (ModelAPIError, FallbackExceptionGroup)):
        return "llm_indisponivel"
    if isinstance(erro, (DBAPIError, TimeoutPool)):
        return "banco_indisponivel"
    return "erro_interno"


def payload_auditavel(dados: BaseModel) -> dict[str, Any]:
    """Payload confirmado, com a imagem reduzida a metadados.

    Bytes de imagem nunca vao para a auditoria: e o app_db que o time
    consulta para metrica, nao um arquivo de midia.
    """
    if isinstance(dados, ProdutoCadastro):
        payload = dados.model_dump(mode="json", exclude={"imagem"})
        payload["imagem"] = {"mime": dados.imagem.mime, "tamanho_bytes": dados.imagem.tamanho_bytes}
        return payload
    return dados.model_dump(mode="json")


async def registrar_interpretacao(
    *,
    usuario: str,
    mensagem: str,
    modelo: str,
    saida: Interpretacao | None,
    erro: BaseException | None,
    duracao_ms: int,
    trace_id: str | None = None,
    prompt_versao: int | None = None,
) -> uuid.UUID | None:
    try:
        async with sessao_app() as sessao:
            return await auditoria_repository.inserir_interpretacao(
                sessao,
                usuario=usuario,
                mensagem=mensagem,
                modelo=modelo,
                tipo=tipo_da_interpretacao(saida) if saida is not None else None,
                proposta=saida.model_dump(mode="json") if saida is not None else None,
                erro=categoria_do_erro(erro) if erro is not None else None,
                duracao_ms=duracao_ms,
                trace_id=trace_id,
                prompt_versao=prompt_versao,
            )
    except Exception:
        logger.exception("Falha ao auditar interpretacao de %s", usuario)
        return None


async def registrar_cadastro(
    *,
    usuario: str,
    entidade: Entidade,
    payload: dict[str, Any],
    resultado: Resultado,
    interpretacao_id: uuid.UUID | None = None,
    entidade_id: int | None = None,
    campo_erro: str | None = None,
    chave_idempotencia: str | None = None,
    resposta: dict[str, Any] | None = None,
) -> None:
    try:
        async with sessao_app() as sessao:
            # Id de interpretacao que nao existe (formulario adulterado ou
            # auditoria anterior que falhou) nao pode derrubar o registro pela FK.
            if interpretacao_id is not None and not await auditoria_repository.interpretacao_existe(
                sessao, interpretacao_id
            ):
                interpretacao_id = None
            await auditoria_repository.inserir_cadastro(
                sessao,
                usuario=usuario,
                entidade=entidade,
                payload=payload,
                resultado=resultado,
                interpretacao_id=interpretacao_id,
                entidade_id=entidade_id,
                campo_erro=campo_erro,
                chave_idempotencia=chave_idempotencia,
                resposta=resposta,
            )
    except Exception:
        logger.exception("Falha ao auditar cadastro de %s por %s", entidade, usuario)


async def resposta_idempotente(usuario: str, chave: str) -> dict[str, Any] | None:
    """Resposta ja devolvida para esta chave, ou None.

    Aqui a falha NAO e engolida: sem saber se a chave ja foi usada, gravar
    de novo poderia duplicar o cadastro.
    """
    async with sessao_app() as sessao:
        return await auditoria_repository.buscar_resposta_idempotente(sessao, usuario, chave)
