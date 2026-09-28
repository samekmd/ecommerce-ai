from sqlalchemy.exc import IntegrityError

from ops_agent.database import sessao_escrita
from ops_agent.repositories import cupom as cupom_repository
from ops_agent.schemas.cupom import CupomCadastro, CupomCriado
from ops_agent.services.erros import ErroConflito, traduzir_erro_integridade


async def cadastrar(dados: CupomCadastro) -> CupomCriado:
    try:
        async with sessao_escrita() as sessao:
            if await cupom_repository.existe_codigo(sessao, dados.codigo):
                raise ErroConflito("codigo", "Codigo de cupom ja cadastrado")
            cupom = await cupom_repository.inserir(sessao, dados)
    except IntegrityError as erro:
        raise traduzir_erro_integridade(erro) from erro
    return CupomCriado.model_validate(cupom)
