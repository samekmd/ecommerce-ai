"""API HTTP do agente Text-to-SQL.

Nesta fase atende um unico banco alvo (o e-commerce ficticio), resolvido
na subida - o cliente nao escolhe banco.
"""

import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from langchain_core.messages import HumanMessage

from api.schemas import HealthResponse, PerguntaRequest, PerguntaResponse
from src.database.database import encerrar_engine, sessao_app, verificar_conexao
from src.database.executor import FalhaDeInfraestrutura
from src.graph import grafo
from src.logging_config import configurar_logging
from src.observability import tracing
from src.repositories import banco_repository
from src.tools.contexto import ContextoInvalido

logger = logging.getLogger(__name__)

# Mesma chave cadastrada por scripts/seed_catalogo.py. Busca pela chave e
# nao pelo id porque o id depende da ordem de insercao no catalogo.
CHAVE_CONEXAO_LOJA = "TARGET_DB_LOJA"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configurar_logging()

    with sessao_app() as sessao:
        banco = banco_repository.buscar_por_chave_conexao(sessao, CHAVE_CONEXAO_LOJA)
    if banco is None:
        # Falhar na subida em vez de em cada pergunta: sem o catalogo
        # populado nenhuma rota de pergunta funciona.
        raise RuntimeError(
            f"Banco {CHAVE_CONEXAO_LOJA} nao cadastrado no catalogo - rode "
            "`PYTHONPATH=. uv run python scripts/seed_catalogo.py`."
        )
    app.state.banco_id = banco.id
    logger.info("API atendendo banco '%s' (id=%s).", banco.nome, banco.id)

    yield

    encerrar_engine()


app = FastAPI(title="Agente Text-to-SQL", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    app_db = verificar_conexao()
    return HealthResponse(status="ok" if app_db else "degradado", app_db=app_db)


# def sincrono de proposito: grafo.invoke bloqueia durante o loop ReAct
# inteiro, e o FastAPI roda rotas sincronas no threadpool em vez de
# travar o event loop.
@app.post("/perguntas", response_model=PerguntaResponse)
def perguntar(corpo: PerguntaRequest, request: Request) -> PerguntaResponse:
    thread_id = corpo.thread_id or str(uuid.uuid4())
    config = tracing.config_do_grafo(thread_id, request.app.state.banco_id)

    try:
        estado = grafo.invoke({"messages": [HumanMessage(corpo.pergunta)]}, config=config)
    except ContextoInvalido:
        logger.exception("Erro de wiring ao invocar o grafo.")
        raise HTTPException(status_code=500, detail="Erro de configuracao interna.")
    except FalhaDeInfraestrutura as erro:
        logger.exception("Falha de infraestrutura no banco alvo.")
        raise HTTPException(status_code=503, detail=f"Falha de infraestrutura no banco alvo: {erro}")
    except Exception as erro:  # ex.: erro de rede/API do provedor de LLM
        logger.exception("Erro ao chamar o agente.")
        raise HTTPException(status_code=502, detail=f"Erro ao chamar o agente: {erro}")

    return PerguntaResponse(resposta=estado["messages"][-1].content, thread_id=thread_id)
