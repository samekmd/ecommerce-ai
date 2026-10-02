"""Traducao de excecoes em resposta HTTP.

Formato unico para o formulario: {"erros": [{"campo", "mensagem"}]}.
Nenhuma resposta ecoa o valor enviado nem a mensagem de uma excecao
inesperada.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic_ai.exceptions import (
    FallbackExceptionGroup,
    ModelAPIError,
    UnexpectedModelBehavior,
    UsageLimitExceeded,
)
from sqlalchemy.exc import OperationalError, TimeoutError as TimeoutPool

from ops_agent.services.erros import ErroCadastro, ErroConflito

logger = logging.getLogger(__name__)


def resposta_de_campo(status_code: int, campo: str | None, mensagem: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content={"erros": [{"campo": campo, "mensagem": mensagem}]}
    )


def _erro_cadastro(_request: Request, erro: ErroCadastro) -> JSONResponse:
    codigo = status.HTTP_409_CONFLICT if isinstance(erro, ErroConflito) else 422
    return resposta_de_campo(codigo, erro.campo, erro.mensagem)


def _validacao(_request: Request, erro: RequestValidationError) -> JSONResponse:
    # O padrao do FastAPI devolve "input": ecoaria o base64 da imagem e o
    # CNPJ digitado. Aqui so o campo e a mensagem.
    erros = []
    for item in erro.errors():
        local = [str(parte) for parte in item.get("loc", ()) if parte not in ("body", "header", "query")]
        erros.append({"campo": ".".join(local) or None, "mensagem": item.get("msg", "invalido")})
    return JSONResponse(status_code=422, content={"erros": erros})


def _agente_falhou(_request: Request, erro: Exception) -> JSONResponse:
    logger.warning("Agente nao produziu proposta valida: %s", type(erro).__name__)
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"erro": "O agente nao conseguiu interpretar a frase. Tente reformular."},
    )


def _llm_indisponivel(_request: Request, erro: Exception) -> JSONResponse:
    logger.warning("LLM indisponivel: %s", type(erro).__name__)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"erro": "Servico de interpretacao indisponivel. Tente novamente."},
    )


def _banco_indisponivel(_request: Request, erro: Exception) -> JSONResponse:
    logger.error("Banco indisponivel: %s", type(erro).__name__)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"erro": "Banco de dados indisponivel. Tente novamente."},
    )


def _inesperado(_request: Request, erro: Exception) -> JSONResponse:
    logger.exception("Erro inesperado", exc_info=erro)
    return JSONResponse(status_code=500, content={"erro": "Erro interno"})


def registrar_tratadores(app: FastAPI) -> None:
    app.add_exception_handler(ErroCadastro, _erro_cadastro)
    app.add_exception_handler(RequestValidationError, _validacao)
    app.add_exception_handler(UnexpectedModelBehavior, _agente_falhou)
    app.add_exception_handler(UsageLimitExceeded, _agente_falhou)
    app.add_exception_handler(ModelAPIError, _llm_indisponivel)
    # Groq e o fallback do OpenRouter falharam: o FallbackModel agrupa os erros.
    app.add_exception_handler(FallbackExceptionGroup, _llm_indisponivel)
    app.add_exception_handler(OperationalError, _banco_indisponivel)
    app.add_exception_handler(TimeoutPool, _banco_indisponivel)
    app.add_exception_handler(Exception, _inesperado)
