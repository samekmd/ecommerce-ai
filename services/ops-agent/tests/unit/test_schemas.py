import base64
from datetime import date
from decimal import Decimal

import pytest
from pydantic import BaseModel, ValidationError

from ops_agent.schemas.categoria import CategoriaProposta
from ops_agent.schemas.comum import PropostaBase
from ops_agent.schemas.cupom import CupomCadastro, CupomProposta
from ops_agent.schemas.fornecedor import FornecedorCadastro, FornecedorProposta
from ops_agent.schemas.interpretacao import (
    PedidoEsclarecimento,
    RespostaInterpretar,
    tipo_da_interpretacao,
)
from ops_agent.schemas.produto import ImagemCadastro, ProdutoCadastro, ProdutoProposta

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 8
GIF = b"GIF89a" + b"\x00" * 16


def b64(conteudo: bytes) -> str:
    return base64.b64encode(conteudo).decode()


def fornecedor(**campos):
    dados = {"nome": "XYZ Ltda", "cnpj": "11.222.333/0001-81", "cidade": "Campinas", "estado": "SP"}
    return FornecedorCadastro(**(dados | campos))


def produto(**campos):
    dados = {
        "nome": "Camisa Nike",
        "sku": "MOD-000001",
        "preco": "100.00",
        "estoque": 5,
        "categoria_id": 1,
        "fornecedor_id": 1,
        "imagem": {"conteudo_base64": b64(PNG)},
    }
    return ProdutoCadastro(**(dados | campos))


def cupom(**campos):
    dados = {
        "codigo": "black10",
        "percentual_desconto": "10",
        "validade_inicio": date(2026, 9, 1),
        "validade_fim": date(2026, 9, 30),
    }
    return CupomCadastro(**(dados | campos))


# --- CNPJ e UF ---------------------------------------------------------


def test_cnpj_com_mascara_normalizado():
    assert fornecedor().cnpj == "11222333000181"


@pytest.mark.parametrize("cnpj", ["11.222.333/0001-82", "00000000000000", "123", "11111111111111"])
def test_cnpj_invalido_recusado(cnpj):
    with pytest.raises(ValidationError, match="CNPJ invalido"):
        fornecedor(cnpj=cnpj)


def test_uf_normalizada_e_validada():
    assert fornecedor(estado=" sp ").estado == "SP"
    with pytest.raises(ValidationError, match="UF invalida"):
        fornecedor(estado="XX")


def test_telefone_normalizado():
    assert fornecedor(telefone="(11) 98765-4321").telefone == "11987654321"
    with pytest.raises(ValidationError, match="telefone"):
        fornecedor(telefone="1234")


def test_email_invalido_recusado():
    with pytest.raises(ValidationError):
        fornecedor(email_contato="nao-e-email")


# --- Produto ------------------------------------------------------------


def test_produto_valido():
    cadastro = produto(preco=Decimal("10.5"))
    assert cadastro.preco == Decimal("10.5")
    assert cadastro.imagem.mime == "image/png"
    assert cadastro.imagem.conteudo == PNG


@pytest.mark.parametrize("preco", ["0", "-1", "100000000.00", "10.999"])
def test_preco_invalido_recusado(preco):
    with pytest.raises(ValidationError, match="preco"):
        produto(preco=preco)


def test_estoque_negativo_recusado():
    with pytest.raises(ValidationError, match="estoque"):
        produto(estoque=-1)


def test_produto_sem_imagem_recusado():
    dados = produto().model_dump(exclude={"imagem"})
    with pytest.raises(ValidationError, match="imagem"):
        ProdutoCadastro(**dados)


def test_campo_extra_recusado():
    with pytest.raises(ValidationError, match="Extra inputs"):
        produto(ativo=False)


# --- Imagem -------------------------------------------------------------


@pytest.mark.parametrize(
    ("conteudo", "mime"), [(PNG, "image/png"), (JPEG, "image/jpeg"), (WEBP, "image/webp")]
)
def test_imagem_detectada_por_magic_bytes(conteudo, mime):
    imagem = ImagemCadastro(conteudo_base64=b64(conteudo))
    assert imagem.mime == mime
    assert imagem.tamanho_bytes == len(conteudo)


def test_prefixo_data_ignorado_na_deteccao():
    # O prefixo diz jpeg, os bytes sao PNG: vale o que os bytes dizem.
    imagem = ImagemCadastro(conteudo_base64=f"data:image/jpeg;base64,{b64(PNG)}")
    assert imagem.mime == "image/png"


@pytest.mark.parametrize(
    ("conteudo_base64", "erro"),
    [
        (b64(GIF), "JPEG, PNG ou WebP"),
        (b64(b"texto qualquer"), "JPEG, PNG ou WebP"),
        ("isso nao e base64!!", "base64"),
    ],
)
def test_imagem_invalida_recusada(conteudo_base64, erro):
    with pytest.raises(ValidationError, match=erro):
        ImagemCadastro(conteudo_base64=conteudo_base64)


def test_imagem_nao_aparece_no_repr():
    assert b64(PNG) not in repr(ImagemCadastro(conteudo_base64=b64(PNG)))


# --- Cupom --------------------------------------------------------------


def test_codigo_cupom_em_maiusculas():
    assert cupom(codigo=" black10 ").codigo == "BLACK10"


@pytest.mark.parametrize("percentual", ["0", "100.01", "-5"])
def test_percentual_invalido_recusado(percentual):
    with pytest.raises(ValidationError, match="percentual_desconto"):
        cupom(percentual_desconto=percentual)


def test_percentual_100_aceito():
    assert cupom(percentual_desconto="100").percentual_desconto == Decimal("100")


def test_validade_invertida_recusada():
    with pytest.raises(ValidationError, match="validade_fim"):
        cupom(validade_inicio=date(2026, 9, 30), validade_fim=date(2026, 9, 1))


def test_codigo_com_espaco_recusado():
    with pytest.raises(ValidationError, match="codigo"):
        cupom(codigo="BLACK 10")


# --- Propostas e interpretacao -----------------------------------------

PROPOSTAS: list[type[BaseModel]] = [
    ProdutoProposta,
    FornecedorProposta,
    CategoriaProposta,
    CupomProposta,
    PedidoEsclarecimento,
]


@pytest.mark.parametrize("classe", PROPOSTAS)
def test_todo_campo_de_proposta_tem_description(classe):
    # E o texto que o LLM le para preencher o campo.
    sem_descricao = [nome for nome, campo in classe.model_fields.items() if not campo.description]
    assert sem_descricao == []


def test_proposta_aceita_campos_ausentes():
    proposta = ProdutoProposta(nome="Camisa")
    assert proposta.preco is None
    assert proposta.avisos == []
    assert isinstance(proposta, PropostaBase)


def test_tipo_da_interpretacao():
    assert tipo_da_interpretacao(CupomProposta()) == "cupom"
    esclarecimento = PedidoEsclarecimento(motivo="nao_suportado", mensagem="So percentual")
    assert tipo_da_interpretacao(esclarecimento) == "esclarecimento"


def test_resposta_serializa_proposta_concreta():
    resposta = RespostaInterpretar(
        tipo="produto", proposta=ProdutoProposta(nome="Camisa", preco="100"), avisos=[]
    )
    assert resposta.model_dump(mode="json")["proposta"]["preco"] == "100"
