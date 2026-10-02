import unicodedata

from sqlalchemy.exc import IntegrityError

from ops_agent.config import obter_configuracao
from ops_agent.database import sessao_escrita, sessao_leitura
from ops_agent.repositories import categoria as categoria_repository
from ops_agent.repositories import fornecedor as fornecedor_repository
from ops_agent.repositories import produto as produto_repository
from ops_agent.schemas.produto import ProdutoCadastro, ProdutoCriado, SkuSugerido
from ops_agent.services.erros import ErroConflito, ErroValidacao, traduzir_erro_integridade

PREFIXO_PADRAO = "SKU"


def prefixo_sku(nome_categoria: str | None) -> str:
    """Tres primeiras letras da categoria, sem acento: "Vestuario" -> "VES"."""
    if not nome_categoria:
        return PREFIXO_PADRAO
    sem_acento = unicodedata.normalize("NFKD", nome_categoria).encode("ascii", "ignore").decode()
    letras = "".join(c for c in sem_acento if c.isalpha()).upper()
    return letras[:3] if len(letras) >= 3 else PREFIXO_PADRAO


async def sugerir_sku(categoria_id: int | None) -> SkuSugerido:
    """Sugestao para o formulario; o usuario pode editar e o UNIQUE decide."""
    async with sessao_leitura() as sessao:
        nome = None
        if categoria_id is not None:
            nome = await categoria_repository.obter_nome(sessao, categoria_id)
        sku = await produto_repository.proximo_sku(sessao, prefixo_sku(nome))
    return SkuSugerido(sku=sku)


async def cadastrar(dados: ProdutoCadastro) -> ProdutoCriado:
    # Antes de abrir a transacao: nao segura conexao para recusar pelo tamanho.
    limite = obter_configuracao().ops_imagem_max_bytes
    if dados.imagem.tamanho_bytes > limite:
        raise ErroValidacao("imagem", f"Imagem maior que o limite de {limite // 1024} KB")

    try:
        async with sessao_escrita() as sessao:
            if not await categoria_repository.existe(sessao, dados.categoria_id):
                raise ErroValidacao("categoria_id", "Categoria inexistente")
            # A FK aceitaria fornecedor inativo; a regra de negocio nao.
            if not await fornecedor_repository.existe_ativo(sessao, dados.fornecedor_id):
                raise ErroValidacao("fornecedor_id", "Fornecedor inexistente ou inativo")
            if await produto_repository.existe_sku(sessao, dados.sku):
                raise ErroConflito("sku", "SKU ja cadastrado")

            # Mesma sessao, mesma transacao: produto sem imagem nunca fica gravado.
            produto = await produto_repository.inserir(sessao, dados)
            await produto_repository.inserir_imagem(
                sessao, produto.id, dados.imagem.conteudo, dados.imagem.mime
            )
    except IntegrityError as erro:
        raise traduzir_erro_integridade(erro) from erro
    return ProdutoCriado.model_validate(produto)
