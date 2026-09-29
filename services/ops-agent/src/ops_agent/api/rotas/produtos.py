from fastapi import APIRouter, Query, status

from ops_agent.api.dependencias import ChaveIdempotencia, InterpretacaoId, UsuarioAtual
from ops_agent.api.rotas._cadastro import cadastrar_com_auditoria
from ops_agent.schemas.comum import MAX_INTEGER
from ops_agent.schemas.produto import ProdutoCadastro, ProdutoCriado, SkuSugerido
from ops_agent.services import produto as produto_service

router = APIRouter(prefix="/produtos", tags=["produtos"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ProdutoCriado)
async def cadastrar_produto(
    dados: ProdutoCadastro,
    usuario: UsuarioAtual,
    interpretacao_id: InterpretacaoId = None,
    chave: ChaveIdempotencia = None,
):
    return await cadastrar_com_auditoria(
        entidade="produto",
        dados=dados,
        cadastrar=produto_service.cadastrar,
        usuario=usuario,
        interpretacao_id=interpretacao_id,
        chave=chave,
    )


@router.get("/sku-sugerido", response_model=SkuSugerido)
async def sugerir_sku(
    categoria_id: int | None = Query(default=None, gt=0, le=MAX_INTEGER),
) -> SkuSugerido:
    return await produto_service.sugerir_sku(categoria_id)
