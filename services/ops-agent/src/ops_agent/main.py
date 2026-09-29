"""Aplicacao FastAPI do ops-agent.

Sem instancia no import: rode com
    uvicorn ops_agent.main:criar_app --factory --port 8001
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ops_agent.api.erros import registrar_tratadores
from ops_agent.api.limite_corpo import LimiteCorpo
from ops_agent.api.rotas import ROUTERS_V1, saude
from ops_agent.config import obter_configuracao
from ops_agent.database import encerrar_engines
from ops_agent.observabilidade import setup as observabilidade

# Margem para o JSON em volta da imagem (nome, sku, preco...).
_MARGEM_CORPO = 64 * 1024


@asynccontextmanager
async def _ciclo_de_vida(_app: FastAPI) -> AsyncIterator[None]:
    yield
    await encerrar_engines()
    # Flush dos spans pendentes: sem isso os ultimos traces se perdem.
    observabilidade.encerrar()


def criar_app() -> FastAPI:
    # Config carregada aqui: configuracao invalida impede a subida, em vez
    # de estourar na primeira requisicao.
    configuracao = obter_configuracao()
    logging.basicConfig(level=configuracao.log_level)
    # Spans do Pydantic AI para o Langfuse; no-op sem credenciais.
    observabilidade.instrumentar_agente()

    app = FastAPI(
        title="ops-agent",
        description="Frase -> proposta estruturada -> confirmacao humana -> cadastro.",
        lifespan=_ciclo_de_vida,
        # Documentacao interativa so fora de producao.
        docs_url=None if configuracao.em_producao else "/docs",
        redoc_url=None,
        openapi_url=None if configuracao.em_producao else "/openapi.json",
    )

    # Base64 e ~4/3 dos bytes da imagem.
    app.add_middleware(
        LimiteCorpo, max_bytes=configuracao.ops_imagem_max_bytes * 4 // 3 + _MARGEM_CORPO
    )
    # Adicionado por ultimo = mais externo: ate o 413 do LimiteCorpo sai com
    # os headers de CORS, senao o navegador nao consegue ler o erro.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=configuracao.ops_cors_origens,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Usuario", "X-Interpretacao-Id", "Idempotency-Key"],
    )
    registrar_tratadores(app)

    app.include_router(saude.router)
    for router in ROUTERS_V1:
        app.include_router(router, prefix="/api/v1")
    return app
