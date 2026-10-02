from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ops_agent.database import verificar_conexoes

router = APIRouter(tags=["saude"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness: o processo responde. Nao toca no banco de proposito."""
    return {"status": "ok"}


@router.get("/ready")
async def ready() -> JSONResponse:
    """Readiness: os tres bancos respondem."""
    bancos = await verificar_conexoes()
    pronto = all(bancos.values())
    return JSONResponse(
        status_code=200 if pronto else 503,
        content={"status": "ok" if pronto else "indisponivel", "bancos": bancos},
    )
