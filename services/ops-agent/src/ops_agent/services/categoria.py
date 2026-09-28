from sqlalchemy.exc import IntegrityError

from ops_agent.database import sessao_escrita, sessao_leitura
from ops_agent.repositories import categoria as categoria_repository
from ops_agent.schemas.categoria import CategoriaCadastro, CategoriaCriada, CategoriaResumo
from ops_agent.services.erros import ErroConflito, ErroValidacao, traduzir_erro_integridade


async def cadastrar(dados: CategoriaCadastro) -> CategoriaCriada:
    try:
        async with sessao_escrita() as sessao:
            # O UNIQUE do banco diferencia caixa: "camisas" passaria com
            # "Camisas" ja cadastrada.
            if await categoria_repository.existe_nome(sessao, dados.nome):
                raise ErroConflito("nome", "Categoria ja cadastrada")
            if dados.categoria_pai_id is not None and not await categoria_repository.existe(
                sessao, dados.categoria_pai_id
            ):
                raise ErroValidacao("categoria_pai_id", "Categoria pai inexistente")
            categoria = await categoria_repository.inserir(sessao, dados)
    except IntegrityError as erro:
        raise traduzir_erro_integridade(erro) from erro
    return CategoriaCriada.model_validate(categoria)


async def listar() -> list[CategoriaResumo]:
    async with sessao_leitura() as sessao:
        return await categoria_repository.listar_com_caminho(sessao)
