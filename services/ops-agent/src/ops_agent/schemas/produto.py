import base64
import binascii
import re
from decimal import Decimal

from pydantic import Field, PrivateAttr, model_validator

from ops_agent.schemas.comum import (
    CadastroBase,
    CriadoBase,
    IdPositivo,
    ModeloBase,
    NumeroProposta,
    Preco,
    PropostaBase,
    Quantidade,
    TextoObrigatorio,
)

_PREFIXO_DATA_URL = re.compile(r"^data:[^,]*;base64,", re.IGNORECASE)


def detectar_mime(conteudo: bytes) -> str | None:
    """Tipo real pelos magic bytes; extensao e prefixo data: mentem."""
    if conteudo.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if conteudo.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if conteudo[:4] == b"RIFF" and conteudo[8:12] == b"WEBP":
        return "image/webp"
    return None


class ProdutoProposta(PropostaBase):
    nome: str = Field(description="Nome do produto, sem quantidade nem preco.")
    preco: NumeroProposta | None = Field(
        default=None,
        gt=0,
        description=(
            "Preco unitario em reais, numero com ate 2 casas (\"cem reais\" -> 100.00). "
            "Null se a frase nao trouxer."
        ),
    )
    estoque: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Quantidade em estoque de UM produto: \"5 camisas\" -> 5. Nunca crie varios produtos."
        ),
    )
    categoria_id: int | None = Field(
        default=None,
        description=(
            "ID de listar_categorias, preferindo a categoria folha. Null se nenhuma encaixar; "
            "nunca invente ID nem crie categoria. Confianca baixa -> aviso."
        ),
    )
    fornecedor_id: int | None = Field(
        default=None,
        description=(
            "ID de buscar_fornecedores. Null se o fornecedor nao for encontrado, com aviso."
        ),
    )
    fornecedor_citado: str | None = Field(
        default=None,
        description="Nome do fornecedor exatamente como citado na frase, mesmo sem ID.",
    )


class ImagemCadastro(CadastroBase):
    """Imagem em base64 (transporte). Decodificada e validada aqui; gravada em bytes.

    O limite de tamanho depende do config e e checado no service.
    """

    conteudo_base64: str = Field(repr=False, min_length=1)

    _conteudo: bytes = PrivateAttr()
    _mime: str = PrivateAttr()

    @model_validator(mode="after")
    def _decodificar(self) -> "ImagemCadastro":
        # O prefixo data: e descartado sem ler o mime que ele declara.
        texto = _PREFIXO_DATA_URL.sub("", self.conteudo_base64)
        texto = re.sub(r"\s", "", texto)
        try:
            conteudo = base64.b64decode(texto, validate=True)
        except (binascii.Error, ValueError) as erro:
            raise ValueError("imagem nao e base64 valido") from erro

        mime = detectar_mime(conteudo)
        if mime is None:
            raise ValueError("imagem deve ser JPEG, PNG ou WebP")

        self._conteudo = conteudo
        self._mime = mime
        return self

    @property
    def conteudo(self) -> bytes:
        return self._conteudo

    @property
    def mime(self) -> str:
        return self._mime

    @property
    def tamanho_bytes(self) -> int:
        return len(self._conteudo)


class ProdutoCadastro(CadastroBase):
    nome: TextoObrigatorio
    sku: TextoObrigatorio
    preco: Preco
    estoque: Quantidade
    categoria_id: IdPositivo
    fornecedor_id: IdPositivo
    imagem: ImagemCadastro


class ProdutoCriado(CriadoBase):
    id: int
    nome: str
    sku: str
    preco: Decimal
    estoque: int
    categoria_id: int
    fornecedor_id: int


class SkuSugerido(ModeloBase):
    sku: str
