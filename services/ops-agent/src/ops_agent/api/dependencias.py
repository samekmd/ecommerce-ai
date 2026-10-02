"""Headers comuns das rotas."""

import uuid
from typing import Annotated

from fastapi import Header

# Identifica quem fez a acao na auditoria. Nao e autenticacao: no MVP o
# frontend envia o identificador e ninguem o confere.
UsuarioAtual = Annotated[
    str,
    Header(alias="X-Usuario", min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._@-]+$"),
]

# Id devolvido pelo /interpretar; liga a proposta ao cadastro confirmado.
InterpretacaoId = Annotated[uuid.UUID | None, Header(alias="X-Interpretacao-Id")]

ChaveIdempotencia = Annotated[
    str | None, Header(alias="Idempotency-Key", min_length=1, max_length=200)
]
