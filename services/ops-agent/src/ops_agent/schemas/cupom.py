from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BeforeValidator, Field, model_validator

from ops_agent.schemas.comum import CadastroBase, CriadoBase, ModeloBase, Percentual, PropostaBase


def normalizar_codigo(valor: object) -> object:
    # UNIQUE do banco diferencia caixa: "promo10" e "PROMO10" passariam.
    return valor.strip().upper() if isinstance(valor, str) else valor


CodigoCupom = Annotated[
    str, BeforeValidator(normalizar_codigo), Field(pattern=r"^[A-Z0-9_-]{3,30}$")
]


class CupomProposta(PropostaBase):
    codigo: str | None = Field(
        default=None, description="Codigo do cupom como citado (ex.: BLACK10). Null se ausente."
    )
    percentual_desconto: Decimal | None = Field(
        default=None,
        gt=0,
        le=100,
        description=(
            "Desconto PERCENTUAL, entre 0 e 100. Desconto em reais nao e suportado: nesse caso "
            "responda com PedidoEsclarecimento, nunca converta para percentual."
        ),
    )
    validade_inicio: date | None = Field(
        default=None,
        description="Inicio da validade (AAAA-MM-DD). Se a frase nao disser, use a data de hoje.",
    )
    validade_fim: date | None = Field(
        default=None,
        description=(
            "Fim da validade (AAAA-MM-DD). Datas relativas (\"ate o fim do mes\") calculadas a "
            "partir da data de hoje informada. Null + aviso se ausente."
        ),
    )


class CupomCadastro(CadastroBase):
    codigo: CodigoCupom
    percentual_desconto: Percentual
    validade_inicio: date
    validade_fim: date

    @model_validator(mode="after")
    def _validar_periodo(self) -> "CupomCadastro":
        if self.validade_fim < self.validade_inicio:
            raise ValueError("validade_fim deve ser igual ou posterior a validade_inicio")
        return self


class CupomCriado(CriadoBase):
    id: int
    codigo: str
    percentual_desconto: Decimal
    validade_inicio: date
    validade_fim: date
    ativo: bool


class VerificacaoCodigoCupom(ModeloBase):
    """Resultado de verificar_codigo_cupom."""

    codigo: str
    existe: bool
