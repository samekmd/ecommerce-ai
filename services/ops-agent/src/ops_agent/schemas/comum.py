"""Bases e tipos reutilizados pelos schemas das entidades.

Nenhum modulo de schemas importa outras camadas: os tipos aqui sao o
contrato entre LLM, formulario e services.
"""

import re
from decimal import Decimal
from typing import Annotated

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field, WithJsonSchema

# Teto do INTEGER do Postgres: acima disso o INSERT falharia com erro de
# overflow em vez de um 422 com o nome do campo.
MAX_INTEGER = 2_147_483_647

UFS = frozenset(
    {
        "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA",
        "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
    }
)

_PESOS_CNPJ = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)


class ModeloBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class CadastroBase(ModeloBase):
    """Payload do formulario: entrada nao confiavel, campo desconhecido e erro."""

    model_config = ConfigDict(extra="forbid")


class CriadoBase(ModeloBase):
    """Resposta da gravacao, montada a partir do model SQLAlchemy."""

    model_config = ConfigDict(from_attributes=True)


class PropostaBase(ModeloBase):
    avisos: list[str] = Field(
        default_factory=list,
        description=(
            "Pontos que o usuario precisa conferir ou completar no formulario: campos "
            "ausentes na frase, escolha de baixa confianca, valor ambiguo. Frases curtas."
        ),
    )


def normalizar_cnpj(valor: str) -> str:
    return re.sub(r"\D", "", valor)


def _digito_cnpj(base: str, pesos: tuple[int, ...]) -> str:
    resto = sum(int(d) * p for d, p in zip(base, pesos, strict=True)) % 11
    return "0" if resto < 2 else str(11 - resto)


def cnpj_valido(cnpj: str) -> bool:
    """Confere os dois digitos verificadores de um CNPJ ja normalizado."""
    if len(cnpj) != 14 or not cnpj.isdigit() or len(set(cnpj)) == 1:
        return False
    primeiro = _digito_cnpj(cnpj[:12], _PESOS_CNPJ)
    segundo = _digito_cnpj(cnpj[:12] + primeiro, (6, *_PESOS_CNPJ))
    return cnpj[12:] == primeiro + segundo


def _validar_cnpj(valor: str) -> str:
    # O banco nao valida CNPJ: guarda 14 digitos e so o UNIQUE.
    cnpj = normalizar_cnpj(valor)
    if not cnpj_valido(cnpj):
        raise ValueError("CNPJ invalido")
    return cnpj


def _validar_uf(valor: str) -> str:
    # O CHECK do banco so olha o tamanho: "XX" passaria.
    if valor not in UFS:
        raise ValueError("UF invalida")
    return valor


def _maiusculas(valor: object) -> object:
    return valor.strip().upper() if isinstance(valor, str) else valor


# Valor numerico que o LLM preenche: valida como Decimal, mas o JSON schema
# e so "number". O schema padrao de Decimal inclui uma alternativa string
# com regex de lookahead que derruba provedores ao converter a tool (medido:
# 502 no endpoint da NVIDIA via OpenRouter). Os *Cadastro seguem com Decimal
# puro: o formulario pode mandar string.
NumeroProposta = Annotated[Decimal, WithJsonSchema({"type": "number"})]

Preco = Annotated[Decimal, Field(gt=0, max_digits=10, decimal_places=2)]
Percentual = Annotated[Decimal, Field(gt=0, le=100, max_digits=5, decimal_places=2)]
TextoObrigatorio = Annotated[str, Field(min_length=1)]
IdPositivo = Annotated[int, Field(gt=0, le=MAX_INTEGER)]
Quantidade = Annotated[int, Field(ge=0, le=MAX_INTEGER)]
Cnpj = Annotated[str, AfterValidator(_validar_cnpj)]
UF = Annotated[str, BeforeValidator(_maiusculas), AfterValidator(_validar_uf)]
