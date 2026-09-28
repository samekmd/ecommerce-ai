import re
from typing import Annotated

from pydantic import AfterValidator, EmailStr, Field

from ops_agent.schemas.comum import (
    UF,
    CadastroBase,
    Cnpj,
    CriadoBase,
    ModeloBase,
    PropostaBase,
    TextoObrigatorio,
)


def _validar_telefone(valor: str) -> str:
    # DDD + numero: 10 digitos (fixo) ou 11 (celular).
    digitos = re.sub(r"\D", "", valor)
    if len(digitos) not in (10, 11):
        raise ValueError("telefone deve ter DDD + numero (10 ou 11 digitos)")
    return digitos


Telefone = Annotated[str, AfterValidator(_validar_telefone)]


class FornecedorProposta(PropostaBase):
    nome: str = Field(description="Razao social ou nome do fornecedor, como citado na frase.")
    cnpj: str | None = Field(
        default=None,
        description=(
            "CNPJ SOMENTE se estiver escrito na frase. Nunca invente nem complete: se ausente, "
            "null e um aviso pedindo o CNPJ."
        ),
    )
    email_contato: str | None = Field(default=None, description="E-mail, se citado na frase.")
    telefone: str | None = Field(default=None, description="Telefone com DDD, se citado.")
    cidade: str | None = Field(default=None, description="Cidade, se citada; senao null + aviso.")
    estado: str | None = Field(
        default=None, description="Sigla da UF (ex.: SP), se citada ou inequivoca pela cidade."
    )


class FornecedorCadastro(CadastroBase):
    nome: TextoObrigatorio
    cnpj: Cnpj
    email_contato: EmailStr | None = None
    telefone: Telefone | None = None
    cidade: TextoObrigatorio
    estado: UF


class FornecedorCriado(CriadoBase):
    id: int
    nome: str
    cnpj: str
    email_contato: str | None
    telefone: str | None
    cidade: str
    estado: str
    ativo: bool


class FornecedorResumo(ModeloBase):
    """Linha de buscar_fornecedores e do GET /fornecedores."""

    id: int
    nome: str
    cidade: str
    estado: str
