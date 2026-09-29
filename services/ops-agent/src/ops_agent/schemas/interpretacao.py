"""Saida do agente e contrato do POST /interpretar."""

import uuid
from typing import Literal

from pydantic import Field

from ops_agent.schemas.categoria import CategoriaProposta
from ops_agent.schemas.comum import ModeloBase
from ops_agent.schemas.cupom import CupomProposta
from ops_agent.schemas.fornecedor import FornecedorProposta
from ops_agent.schemas.produto import ProdutoProposta


class PedidoEsclarecimento(ModeloBase):
    """Quando nao da para propor um cadastro: ambiguo, nao suportado ou fora do escopo."""

    motivo: Literal["ambiguo", "nao_suportado", "fora_do_escopo"] = Field(
        description=(
            "ambiguo: falta informacao para saber o que cadastrar. nao_suportado: pedido "
            "entendido mas nao permitido (desconto em reais, editar, excluir). fora_do_escopo: "
            "nao e cadastro de produto, fornecedor, categoria ou cupom."
        )
    )
    mensagem: str = Field(
        description="Pergunta ou explicacao curta ao usuario, em portugues."
    )


# O tipo escolhido pelo modelo identifica a intencao; nao ha classificador.
Interpretacao = (
    ProdutoProposta | FornecedorProposta | CategoriaProposta | CupomProposta | PedidoEsclarecimento
)

TipoInterpretacao = Literal["produto", "fornecedor", "categoria", "cupom", "esclarecimento"]

_TIPOS: dict[type, TipoInterpretacao] = {
    ProdutoProposta: "produto",
    FornecedorProposta: "fornecedor",
    CategoriaProposta: "categoria",
    CupomProposta: "cupom",
    PedidoEsclarecimento: "esclarecimento",
}


def tipo_da_interpretacao(interpretacao: Interpretacao) -> TipoInterpretacao:
    return _TIPOS[type(interpretacao)]


class RequisicaoInterpretar(ModeloBase):
    mensagem: str = Field(min_length=1, max_length=1000)


class RespostaInterpretar(ModeloBase):
    # Reenviado pelo formulario em X-Interpretacao-Id; liga proposta e
    # confirmacao na auditoria. None se a auditoria falhou.
    interpretacao_id: uuid.UUID | None
    tipo: TipoInterpretacao
    proposta: Interpretacao
    avisos: list[str]
