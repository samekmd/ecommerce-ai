"""Erros de dominio dos cadastros. A camada api/ traduz em 409/422.

Os services nao conhecem HTTP: levantam o erro com o campo do formulario
que o usuario precisa corrigir.
"""

from sqlalchemy.exc import IntegrityError


class ErroCadastro(Exception):
    """Base. `mensagem` e segura para mostrar no formulario."""

    def __init__(self, campo: str | None, mensagem: str) -> None:
        super().__init__(mensagem)
        self.campo = campo
        self.mensagem = mensagem


class ErroConflito(ErroCadastro):
    """Ja existe registro com o valor informado (409)."""


class ErroValidacao(ErroCadastro):
    """Regra que depende do banco ou do config (422)."""


# Nome da constraint -> (erro, campo, mensagem). As uq_/ck_ tem nome
# explicito no DDL; as FKs usam o nome gerado pelo Postgres. Um teste de
# drift confere que toda chave existe no banco.
CONSTRAINTS: dict[str, tuple[type[ErroCadastro], str, str]] = {
    "uq_produtos_sku": (ErroConflito, "sku", "SKU ja cadastrado"),
    "uq_fornecedores_cnpj": (ErroConflito, "cnpj", "CNPJ ja cadastrado"),
    "uq_categorias_nome": (ErroConflito, "nome", "Categoria ja cadastrada"),
    "uq_cupons_codigo": (ErroConflito, "codigo", "Codigo de cupom ja cadastrado"),
    "produtos_imagens_pkey": (ErroConflito, "imagem", "Produto ja possui imagem"),
    "produtos_categoria_id_fkey": (ErroValidacao, "categoria_id", "Categoria inexistente"),
    "produtos_fornecedor_id_fkey": (ErroValidacao, "fornecedor_id", "Fornecedor inexistente"),
    "categorias_categoria_pai_id_fkey": (
        ErroValidacao, "categoria_pai_id", "Categoria pai inexistente",
    ),
    "produtos_imagens_produto_id_fkey": (ErroValidacao, "imagem", "Produto da imagem inexistente"),
    "ck_categorias_pai_diferente_de_si": (
        ErroValidacao, "categoria_pai_id", "Categoria nao pode ser pai de si mesma",
    ),
    "ck_fornecedores_estado_sigla": (ErroValidacao, "estado", "UF deve ter 2 letras"),
    "ck_produtos_preco_positivo": (ErroValidacao, "preco", "Preco deve ser maior que zero"),
    "ck_produtos_estoque_nao_negativo": (ErroValidacao, "estoque", "Estoque nao pode ser negativo"),
    "ck_cupons_percentual_valido": (
        ErroValidacao, "percentual_desconto", "Percentual deve estar entre 0 e 100",
    ),
    "ck_cupons_validade_coerente": (
        ErroValidacao, "validade_fim", "Fim da validade anterior ao inicio",
    ),
    "ck_produtos_imagens_mime_valido": (ErroValidacao, "imagem", "Imagem deve ser JPEG, PNG ou WebP"),
    "ck_produtos_imagens_tamanho_positivo": (ErroValidacao, "imagem", "Imagem vazia"),
    "ck_produtos_imagens_tamanho_coerente": (ErroValidacao, "imagem", "Imagem corrompida"),
}


def traduzir_erro_integridade(erro: IntegrityError) -> Exception:
    """Erro de campo para constraint conhecida; o proprio erro se desconhecida.

    Constraint desconhecida vira 500 generico na API: melhor que apontar
    o campo errado para o usuario.
    """
    diag = getattr(erro.orig, "diag", None)
    nome = getattr(diag, "constraint_name", None)
    if nome not in CONSTRAINTS:
        return erro
    classe, campo, mensagem = CONSTRAINTS[nome]
    return classe(campo, mensagem)
