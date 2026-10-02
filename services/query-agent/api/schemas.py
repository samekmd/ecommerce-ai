"""Payloads de request e response da API HTTP do agente."""

from pydantic import BaseModel, Field


class PerguntaRequest(BaseModel):
    pergunta: str = Field(min_length=1, description="Pergunta em linguagem natural.")
    thread_id: str | None = Field(
        default=None,
        description="Conversa a continuar. Ausente, a API abre uma conversa nova.",
    )


class PerguntaResponse(BaseModel):
    resposta: str
    # Devolvido sempre, inclusive quando gerado aqui: e o que o cliente
    # reenvia para fazer perguntas de acompanhamento na mesma conversa.
    thread_id: str


class HealthResponse(BaseModel):
    status: str
    app_db: bool
