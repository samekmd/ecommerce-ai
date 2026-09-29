"""Sequencia comum dos POSTs de cadastro: idempotencia, service e auditoria."""

import uuid
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ops_agent.services import auditoria
from ops_agent.services.auditoria import Entidade
from ops_agent.services.erros import ErroCadastro, ErroConflito

Criado = TypeVar("Criado", bound=BaseModel)


async def cadastrar_com_auditoria(
    *,
    entidade: Entidade,
    dados: BaseModel,
    cadastrar: Callable[[Any], Awaitable[Criado]],
    usuario: str,
    interpretacao_id: uuid.UUID | None,
    chave: str | None,
) -> Criado | JSONResponse:
    # Repeticao com a mesma chave (ex.: duplo clique, retry de rede) devolve
    # a resposta original sem gravar de novo.
    if chave is not None:
        anterior = await auditoria.resposta_idempotente(usuario, chave)
        if anterior is not None:
            return JSONResponse(status_code=201, content=anterior)

    registro: dict[str, Any] = {
        "usuario": usuario,
        "entidade": entidade,
        "payload": auditoria.payload_auditavel(dados),
        "interpretacao_id": interpretacao_id,
        "chave_idempotencia": chave,
    }
    try:
        criado = await cadastrar(dados)
    except ErroCadastro as erro:
        resultado = "conflito" if isinstance(erro, ErroConflito) else "invalido"
        await auditoria.registrar_cadastro(**registro, resultado=resultado, campo_erro=erro.campo)
        raise
    except Exception:
        await auditoria.registrar_cadastro(**registro, resultado="erro")
        raise

    await auditoria.registrar_cadastro(
        **registro,
        resultado="criado",
        entidade_id=criado.id,
        resposta=criado.model_dump(mode="json"),
    )
    return criado
