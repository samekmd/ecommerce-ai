from sqlalchemy.exc import IntegrityError

from ops_agent.config import obter_configuracao
from ops_agent.database import sessao_escrita, sessao_leitura
from ops_agent.repositories import fornecedor as fornecedor_repository
from ops_agent.schemas.fornecedor import FornecedorCadastro, FornecedorCriado, FornecedorResumo
from ops_agent.services.erros import ErroConflito, traduzir_erro_integridade


async def cadastrar(dados: FornecedorCadastro) -> FornecedorCriado:
    try:
        async with sessao_escrita() as sessao:
            if await fornecedor_repository.existe_cnpj(sessao, dados.cnpj):
                raise ErroConflito("cnpj", "CNPJ ja cadastrado")
            fornecedor = await fornecedor_repository.inserir(sessao, dados)
    except IntegrityError as erro:
        raise traduzir_erro_integridade(erro) from erro
    return FornecedorCriado.model_validate(fornecedor)


async def buscar(termo: str) -> list[FornecedorResumo]:
    limite = obter_configuracao().ops_max_fornecedores_busca
    async with sessao_leitura() as sessao:
        return await fornecedor_repository.buscar_ativos(sessao, termo, limite)
