from fastapi import APIRouter, status

from ops_agent.api.dependencias import ChaveIdempotencia, InterpretacaoId, UsuarioAtual
from ops_agent.api.rotas._cadastro import cadastrar_com_auditoria
from ops_agent.schemas.categoria import CategoriaCadastro, CategoriaCriada, CategoriaResumo
from ops_agent.services import categoria as categoria_service

router = APIRouter(prefix="/categorias", tags=["categorias"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CategoriaCriada)
async def cadastrar_categoria(
    dados: CategoriaCadastro,
    usuario: UsuarioAtual,
    interpretacao_id: InterpretacaoId = None,
    chave: ChaveIdempotencia = None,
):
    return await cadastrar_com_auditoria(
        entidade="categoria",
        dados=dados,
        cadastrar=categoria_service.cadastrar,
        usuario=usuario,
        interpretacao_id=interpretacao_id,
        chave=chave,
    )


@router.get("", response_model=list[CategoriaResumo])
async def listar_categorias() -> list[CategoriaResumo]:
    return await categoria_service.listar()
