"""Middleware ASGI que limita o tamanho do corpo da requisicao.

Sem isso, um base64 de centenas de MB seria lido, parseado e decodificado
antes de o service recusar pelo tamanho da imagem. Conta os bytes do
stream, nao so o Content-Length, que pode faltar num corpo chunked.
"""

import json
from typing import Any

Scope = dict[str, Any]
Receive = Any
Send = Any


class CorpoGrandeDemais(Exception):
    pass


class LimiteCorpo:
    def __init__(self, app: Any, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        declarado = dict(scope.get("headers") or []).get(b"content-length")
        if declarado is not None and declarado.isdigit() and int(declarado) > self.max_bytes:
            await self._recusar(send)
            return

        recebido = 0
        resposta_iniciada = False

        async def receive_limitado() -> dict[str, Any]:
            nonlocal recebido
            mensagem = await receive()
            if mensagem["type"] == "http.request":
                recebido += len(mensagem.get("body", b""))
                if recebido > self.max_bytes:
                    raise CorpoGrandeDemais
            return mensagem

        async def send_rastreado(mensagem: dict[str, Any]) -> None:
            nonlocal resposta_iniciada
            if mensagem["type"] == "http.response.start":
                resposta_iniciada = True
            await send(mensagem)

        try:
            await self.app(scope, receive_limitado, send_rastreado)
        except CorpoGrandeDemais:
            if not resposta_iniciada:
                await self._recusar(send)

    async def _recusar(self, send: Send) -> None:
        corpo = json.dumps({"erro": "Requisicao maior que o limite permitido"}).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(corpo)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": corpo})
