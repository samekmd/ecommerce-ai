from fastapi import APIRouter, Query, status

from ops_agent.api.dependencias import ChaveIdempotencia, InterpretacaoId, UsuarioAtual
from ops_agent.api.rotas._cadastro import cadastrar_com_auditoria
from ops_agent.schemas.fornecedor import FornecedorCadastro, FornecedorCriado, FornecedorResumo
from ops_agent.services import fornecedor as fornecedor_service

router = APIRouter(prefix="/fornecedores", tags=["fornecedores"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=FornecedorCriado)
async def cadastrar_fornecedor(
    dados: FornecedorCadastro,
    usuario: UsuarioAtual,
    interpretacao_id: InterpretacaoId = None,
    chave: ChaveIdempotencia = None,
):
    return await cadastrar_com_auditoria(
        entidade="fornecedor",
        dados=dados,
        cadastrar=fornecedor_service.cadastrar,
        usuario=usuario,
        interpretacao_id=interpretacao_id,
        chave=chave,
    )


@router.get("", response_model=list[FornecedorResumo])
async def buscar_fornecedores(
    termo: str = Query(min_length=2, max_length=100),
) -> list[FornecedorResumo]:
    """Apoio ao formulario quando a proposta veio sem fornecedor_id."""
    return await fornecedor_service.buscar(termo)
