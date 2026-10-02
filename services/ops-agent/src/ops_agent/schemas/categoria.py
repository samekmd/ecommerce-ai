from pydantic import Field

from ops_agent.schemas.comum import (
    CadastroBase,
    CriadoBase,
    IdPositivo,
    ModeloBase,
    PropostaBase,
    TextoObrigatorio,
)


class CategoriaProposta(PropostaBase):
    """Pedido explicito de criar uma categoria nova."""

    nome: str = Field(description="Nome da nova categoria, como o usuario escreveu.")
    categoria_pai_id: int | None = Field(
        default=None,
        description=(
            "ID da categoria pai, obtido de listar_categorias, quando o usuario indicar onde "
            "ela fica. Null para categoria raiz ou se o pai citado nao existir."
        ),
    )


class CategoriaCadastro(CadastroBase):
    nome: TextoObrigatorio
    categoria_pai_id: IdPositivo | None = None


class CategoriaCriada(CriadoBase):
    id: int
    nome: str
    categoria_pai_id: int | None


class CategoriaResumo(ModeloBase):
    """Linha de listar_categorias e do GET /categorias."""

    id: int
    caminho: str
    # O agente prefere a folha: "Camisas" em vez de "Moda".
    folha: bool
