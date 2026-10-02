from fastapi import APIRouter, status

from ops_agent.api.dependencias import ChaveIdempotencia, InterpretacaoId, UsuarioAtual
from ops_agent.api.rotas._cadastro import cadastrar_com_auditoria
from ops_agent.schemas.cupom import CupomCadastro, CupomCriado
from ops_agent.services import cupom as cupom_service

router = APIRouter(prefix="/cupons", tags=["cupons"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CupomCriado)
async def cadastrar_cupom(
    dados: CupomCadastro,
    usuario: UsuarioAtual,
    interpretacao_id: InterpretacaoId = None,
    chave: ChaveIdempotencia = None,
):
    return await cadastrar_com_auditoria(
        entidade="cupom",
        dados=dados,
        cadastrar=cupom_service.cadastrar,
        usuario=usuario,
        interpretacao_id=interpretacao_id,
        chave=chave,
    )
