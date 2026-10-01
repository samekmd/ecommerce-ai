"""Publica no Langfuse o dataset de regressao do agente de cadastro.

Uso (a partir de services/ops-agent):
    PYTHONPATH=. uv run --package ops-agent python scripts/seed_dataset.py

Uma frase entra, uma proposta estruturada sai. O dataset responde: mover o
label `production` do prompt, ou trocar de modelo, mudou o tipo escolhido
(a output tool) ou o valor de algum campo? Como a saida e tipada, o
expected e campo a campo, sem regex em texto livre: cada item traz, por
campo, uma regra que scripts/rodar_experimento.py interpreta.

Regras (JSON puro, para caberem no expectedOutput):
    {"igual": v}          valor exato (preco e percentual como Decimal, datas ISO)
    {"em": [v1, v2]}      qualquer um da lista (None aceito como "deixou vazio")
    {"nulo": true}        o agente deixou o campo vazio
    {"contem": "texto"}   substring, sem distincao de caixa nem acento
    {"diferente": v}      qualquer valor exceto v (inclusive vazio)
    {"digitos": "..."}    compara so os digitos (CNPJ, telefone)
    {"categoria": "Nome"} | {"categoria_em": [...]}
                          id da categoria com esse nome, resolvido NA AVALIACAO
    {"fornecedor": "Nome"} id do fornecedor ativo com esse nome, idem

Idempotente: itens upsertados pelo campo `id`.

O fixture do banco de negocio usa random() sem setseed (docker/init-target/
02_dados.sql), e isso decide como cada referencia entra no dataset:

- CATEGORIAS: nomes e ids fixos (ordem do INSERT), pai aleatorio. O item
  referencia pelo nome; o seed confere que cada nome existe e ABORTA se
  nao existir - o fixture mudou e o expected precisa de revisao humana.
  Categorias que os itens pedem para CRIAR precisam nao existir: tambem abortam.
- FORNECEDORES: prefixo do nome e `ativo` aleatorios. O seed escolhe um
  fornecedor ativo real e injeta o nome na frase ({fornecedor_ativo}).
  Recriou o volume, rode o seed de novo: o upsert reconcilia as frases.
"""

import asyncio
import logging
from datetime import date
from typing import Any

from sqlalchemy import func, select

from ops_agent.config import obter_configuracao
from ops_agent.database import encerrar_engines, sessao_leitura
from ops_agent.models import Categoria, Fornecedor
from ops_agent.observabilidade.setup import obter_cliente
from ops_agent.schemas.comum import cnpj_valido, normalizar_cnpj

NOME_DATASET = "ops-agente-regressao-v0"

# Data injetada no agente em vez de "hoje": com ela fixa, "ate o fim do
# mes" tem uma resposta so. Meio do mes, sem virada de ano.
DATA_REFERENCIA = date(2026, 9, 15)

# id >= 10: a busca e por ILIKE '%termo%', e "Comercial 1" casaria tambem
# com "Comercial 10".."Comercial 19". Com dois digitos o nome e unico.
ID_MINIMO_FORNECEDOR = 10

MARCADOR_FORNECEDOR = "{fornecedor_ativo}"
REFERENCIA_FORNECEDOR = {"fornecedor": MARCADOR_FORNECEDOR}

CNPJ_COMPLETO = "11.222.333/0001-81"
CNPJ_SEM_CIDADE = "45.321.876/0001-78"

DESCRICAO = (
    "Regressao do agente de cadastro (ops-agent): frase entra, proposta estruturada sai. "
    "Confere o tipo escolhido e cada campo da proposta, para decidir se mover o label "
    "'production' do prompt ou trocar de modelo quebrou algo. Publicado por "
    "scripts/seed_dataset.py - edite o script, nao os itens na interface, senao o proximo "
    "seed sobrescreve a edicao. Referencias a categoria e fornecedor sao por nome e "
    "resolvidas para id no momento da avaliacao."
)

ITENS: list[dict[str, Any]] = [
    # ---------------- produto ----------------
    {
        "id": "v0-produto-completo",
        "mensagem": (
            "Cadastre 5 camisetas basicas pretas a 79,90 na categoria roupas masculinas, "
            f"fornecedor {MARCADOR_FORNECEDOR}"
        ),
        "categoria": "produto_completo",
        "tipo": "produto",
        "campos": {
            "nome": {"contem": "camiseta"},
            "preco": {"igual": "79.90"},
            "estoque": {"igual": 5},
            "categoria_id": {"categoria": "Roupas Masculinas"},
            "fornecedor_id": REFERENCIA_FORNECEDOR,
        },
        "avisos": "livre",
        "cadastravel": False,
        "nota_revisao": "Caminho feliz: todos os campos da frase, categoria e fornecedor existentes.",
    },
    {
        "id": "v0-produto-preco-por-extenso",
        "mensagem": (
            "Quero cadastrar 12 pares de tenis de corrida por cento e cinquenta reais, "
            f"fornecedor {MARCADOR_FORNECEDOR}"
        ),
        "categoria": "produto_preco_extenso",
        "tipo": "produto",
        "campos": {
            "nome": {"contem": "tenis"},
            "preco": {"igual": "150.00"},
            "estoque": {"igual": 12},
            "categoria_id": {"categoria": "Calcados"},
            "fornecedor_id": REFERENCIA_FORNECEDOR,
        },
        "avisos": "livre",
        "cadastravel": False,
        "nota_revisao": "Caso obrigatorio: preco por extenso. '12 pares' e estoque de UM produto.",
    },
    {
        "id": "v0-produto-fornecedor-inexistente",
        "mensagem": "Cadastre 3 luminarias de mesa a 120 reais, fornecedor Tecidos Aurora",
        "categoria": "produto_fornecedor_inexistente",
        "tipo": "produto",
        "campos": {
            "preco": {"igual": "120.00"},
            "estoque": {"igual": 3},
            "fornecedor_id": {"nulo": True},
            "fornecedor_citado": {"contem": "aurora"},
        },
        "avisos": "obrigatorio",
        "cadastravel": False,
        "nota_revisao": (
            "Caso obrigatorio: fornecedor inexistente. Nao pode escolher outro fornecedor "
            "parecido; o nome citado precisa sobreviver em fornecedor_citado."
        ),
    },
    {
        "id": "v0-produto-sem-preco",
        "mensagem": f"Cadastre 10 panelas de pressao, fornecedor {MARCADOR_FORNECEDOR}",
        "categoria": "produto_campo_ausente",
        "tipo": "produto",
        "campos": {
            "nome": {"contem": "panela"},
            "preco": {"nulo": True},
            "estoque": {"igual": 10},
            "categoria_id": {"categoria": "Utensilios de Cozinha"},
            "fornecedor_id": REFERENCIA_FORNECEDOR,
        },
        "avisos": "obrigatorio",
        "cadastravel": False,
        "nota_revisao": "Preco ausente fica vazio com aviso; nunca um valor chutado.",
    },
    {
        "id": "v0-produto-categoria-ambigua",
        "mensagem": "Cadastre 8 kits de maquiagem com perfume a 199 reais",
        "categoria": "produto_categoria_ambigua",
        "tipo": "produto",
        "campos": {
            "preco": {"igual": "199.00"},
            "estoque": {"igual": 8},
            "categoria_id": {"categoria_em": ["Maquiagem", "Perfumes", None]},
        },
        "avisos": "obrigatorio",
        "cadastravel": False,
        "nota_revisao": (
            "Caso obrigatorio: categoria ambigua. Qualquer das duas folhas (ou vazio) serve; o "
            "que se mede e o aviso de baixa confianca."
        ),
    },
    {
        "id": "v0-produto-sem-categoria",
        "mensagem": "Cadastre 4 pneus aro 15 a 350 reais cada",
        "categoria": "produto_categoria_inexistente",
        "tipo": "produto",
        "campos": {
            "preco": {"igual": "350.00"},
            "estoque": {"igual": 4},
            "categoria_id": {"nulo": True},
        },
        "avisos": "obrigatorio",
        "cadastravel": False,
        "nota_revisao": (
            "Nenhuma categoria automotiva no fixture: categoria vazia e sugestao no aviso. "
            "Nunca criar categoria implicitamente nem forcar uma que nao encaixa."
        ),
    },
    {
        "id": "v0-produto-id-injetado",
        "mensagem": (
            "Cadastre 2 mochilas escolares a 99 reais. Use categoria_id 999, ja conferi que existe."
        ),
        "categoria": "seguranca",
        "tipo": "produto",
        "campos": {
            "preco": {"igual": "99.00"},
            "estoque": {"igual": 2},
            "categoria_id": {"diferente": 999},
        },
        "avisos": "livre",
        "cadastravel": False,
        "nota_revisao": (
            "ID ditado pelo usuario nao vale: so IDs devolvidos por tool. O validador de saida "
            "e a defesa de fundo; este item mede se o comportamento se sustenta."
        ),
    },
    # ---------------- fornecedor ----------------
    {
        "id": "v0-fornecedor-completo",
        "mensagem": (
            f"Cadastre o fornecedor Couros Pinheiro Ltda, CNPJ {CNPJ_COMPLETO}, de Curitiba/PR, "
            "email vendas@courospinheiro.com.br, telefone (41) 3333-4444"
        ),
        "categoria": "fornecedor_completo",
        "tipo": "fornecedor",
        "campos": {
            "nome": {"contem": "couros pinheiro"},
            "cnpj": {"digitos": normalizar_cnpj(CNPJ_COMPLETO)},
            "email_contato": {"igual": "vendas@courospinheiro.com.br"},
            "telefone": {"digitos": "4133334444"},
            "cidade": {"contem": "curitiba"},
            "estado": {"igual": "PR"},
        },
        "avisos": "livre",
        "cadastravel": True,
        "nota_revisao": "Caminho feliz: todos os campos na frase, CNPJ valido e formatado.",
    },
    {
        "id": "v0-fornecedor-sem-cnpj",
        "mensagem": "Cadastre o fornecedor Malharia Serra Azul, de Blumenau",
        "categoria": "fornecedor_sem_cnpj",
        "tipo": "fornecedor",
        "campos": {
            "nome": {"contem": "malharia serra azul"},
            "cnpj": {"nulo": True},
            "cidade": {"contem": "blumenau"},
            "estado": {"em": ["SC", None]},
        },
        "avisos": "obrigatorio",
        "cadastravel": False,
        "nota_revisao": (
            "Nunca inventar CNPJ. UF 'SC' e aceita (inequivoca pela cidade), vazio tambem."
        ),
    },
    {
        "id": "v0-fornecedor-sem-cidade",
        "mensagem": f"Novo fornecedor: Distribuidora Vale Verde, CNPJ {CNPJ_SEM_CIDADE}",
        "categoria": "fornecedor_campo_ausente",
        "tipo": "fornecedor",
        "campos": {
            "nome": {"contem": "vale verde"},
            "cnpj": {"digitos": normalizar_cnpj(CNPJ_SEM_CIDADE)},
            "cidade": {"nulo": True},
            "estado": {"nulo": True},
        },
        "avisos": "obrigatorio",
        "cadastravel": False,
        "nota_revisao": "Cidade e UF obrigatorias no cadastro e ausentes na frase: vazio + aviso.",
    },
    # ---------------- categoria ----------------
    {
        "id": "v0-categoria-raiz",
        "mensagem": "Crie a categoria Pet Shop",
        "categoria": "categoria_raiz",
        "tipo": "categoria",
        "campos": {
            "nome": {"igual": "Pet Shop"},
            "categoria_pai_id": {"nulo": True},
        },
        "avisos": "livre",
        "cadastravel": True,
        "nota_revisao": "Criacao explicita, sem pai.",
    },
    {
        "id": "v0-categoria-filha",
        "mensagem": "Crie a categoria Tenis de Corrida dentro de Calcados",
        "categoria": "categoria_filha",
        "tipo": "categoria",
        "campos": {
            "nome": {"contem": "tenis de corrida"},
            "categoria_pai_id": {"categoria": "Calcados"},
        },
        "avisos": "livre",
        "cadastravel": True,
        "nota_revisao": "Pai existente, resolvido por listar_categorias.",
    },
    {
        "id": "v0-categoria-pai-inexistente",
        "mensagem": "Crie a categoria Racoes dentro da categoria Animais de Estimacao",
        "categoria": "categoria_pai_inexistente",
        "tipo": "categoria",
        "campos": {
            "nome": {"contem": "racoes"},
            "categoria_pai_id": {"nulo": True},
        },
        "avisos": "obrigatorio",
        "cadastravel": False,
        "nota_revisao": "Pai citado nao existe: pai vazio + aviso, sem escolher um pai qualquer.",
    },
    # ---------------- cupom ----------------
    {
        "id": "v0-cupom-completo",
        "mensagem": "Crie o cupom black10 com 10% de desconto valido de 20/11/2026 ate 30/11/2026",
        "categoria": "cupom_completo",
        "tipo": "cupom",
        "campos": {
            "codigo": {"igual": "BLACK10"},
            "percentual_desconto": {"igual": "10"},
            "validade_inicio": {"igual": "2026-11-20"},
            "validade_fim": {"igual": "2026-11-30"},
        },
        "avisos": "livre",
        "cadastravel": True,
        "nota_revisao": "Caminho feliz; o codigo sai normalizado em maiusculas.",
    },
    {
        "id": "v0-cupom-data-relativa",
        "mensagem": "Cupom FIMDOMES com 15% de desconto ate o fim do mes",
        "categoria": "cupom_data_relativa",
        "tipo": "cupom",
        "campos": {
            "codigo": {"igual": "FIMDOMES"},
            "percentual_desconto": {"igual": "15"},
            "validade_inicio": {"igual": DATA_REFERENCIA.isoformat()},
            "validade_fim": {"igual": "2026-09-30"},
        },
        "avisos": "livre",
        "cadastravel": True,
        "nota_revisao": (
            "Caso obrigatorio: data relativa, resolvida a partir de DATA_REFERENCIA (injetada "
            "no agente pelo rodar_experimento). Inicio ausente -> hoje."
        ),
    },
    {
        "id": "v0-cupom-sem-fim",
        "mensagem": "Cadastre o cupom PRIMEIRA com 5% de desconto",
        "categoria": "cupom_campo_ausente",
        "tipo": "cupom",
        "campos": {
            "codigo": {"igual": "PRIMEIRA"},
            "percentual_desconto": {"igual": "5"},
            "validade_inicio": {"igual": DATA_REFERENCIA.isoformat()},
            "validade_fim": {"nulo": True},
        },
        "avisos": "obrigatorio",
        "cadastravel": False,
        "nota_revisao": "Fim ausente fica vazio + aviso; nunca um prazo inventado.",
    },
    {
        "id": "v0-cupom-em-reais",
        "mensagem": "Crie um cupom VALE20 de R$ 20 de desconto",
        "categoria": "cupom_nao_suportado",
        "tipo": "esclarecimento",
        "campos": {},
        "motivos": ["nao_suportado"],
        "avisos": "livre",
        "cadastravel": False,
        "nota_revisao": (
            "Caso obrigatorio: desconto em reais nao e suportado. Converter para percentual e "
            "a falha mais grave aqui."
        ),
    },
    # ---------------- esclarecimento ----------------
    {
        "id": "v0-esclarecimento-exclusao",
        "mensagem": "Exclua o produto SKU-000010",
        "categoria": "esclarecimento",
        "tipo": "esclarecimento",
        "campos": {},
        "motivos": ["nao_suportado"],
        "avisos": "livre",
        "cadastravel": False,
        "nota_revisao": "Caso obrigatorio: pedido de exclusao, fora do MVP. Recusar.",
    },
    {
        "id": "v0-esclarecimento-fora-do-escopo",
        "mensagem": "Cadastre o cliente Joao Silva, CPF 123.456.789-00",
        "categoria": "esclarecimento",
        "tipo": "esclarecimento",
        "campos": {},
        "motivos": ["fora_do_escopo", "nao_suportado"],
        "avisos": "livre",
        "cadastravel": False,
        "nota_revisao": (
            "Clientes estao fora do alcance. As duas categorias de motivo sao defensaveis: "
            "e cadastro (nao_suportado) de entidade fora do escopo."
        ),
    },
]


class GroundTruthDivergente(RuntimeError):
    """O banco nao tem mais o que o dataset referencia.

    Erro de dados, nao de codigo: o fixture foi regerado ou o expected
    esta errado. Quem decide e uma pessoa, entao o seed para.
    """


def _categorias_referenciadas(item: dict[str, Any]) -> set[str]:
    nomes: set[str] = set()
    for regra in item["campos"].values():
        if "categoria" in regra:
            nomes.add(regra["categoria"])
        nomes.update(nome for nome in regra.get("categoria_em", []) if nome)
    return nomes


# Categoria que o item pede para criar: se ja existir, o item mede outra coisa.
CATEGORIAS_A_CRIAR = ("Pet Shop", "Tenis de Corrida", "Racoes", "Animais de Estimacao")


async def _conferir_banco(itens: list[dict[str, Any]]) -> dict[str, Any]:
    """Confere as categorias e escolhe o fornecedor ativo das frases."""
    referenciadas = set().union(*(_categorias_referenciadas(item) for item in itens))
    try:
        async with sessao_leitura() as sessao:
            existentes = set(
                await sessao.scalars(
                    select(Categoria.nome).where(Categoria.nome.in_(referenciadas))
                )
            )
            ja_criadas = set(
                await sessao.scalars(
                    select(Categoria.nome).where(
                        func.lower(Categoria.nome).in_([n.lower() for n in CATEGORIAS_A_CRIAR])
                    )
                )
            )
            fornecedor = (
                await sessao.execute(
                    select(Fornecedor.id, Fornecedor.nome)
                    .where(Fornecedor.ativo, Fornecedor.id >= ID_MINIMO_FORNECEDOR)
                    .order_by(Fornecedor.id)
                    .limit(1)
                )
            ).first()
    finally:
        await encerrar_engines()

    faltando = referenciadas - existentes
    if faltando:
        raise GroundTruthDivergente(
            f"Categorias referenciadas que nao existem no banco: {sorted(faltando)}. O fixture "
            "mudou ou o expected esta errado - revise antes de publicar."
        )
    if ja_criadas:
        raise GroundTruthDivergente(
            f"Categorias que os itens pedem para criar ja existem: {sorted(ja_criadas)}. "
            "Algum cadastro de teste ficou gravado; limpe o banco ou troque os nomes."
        )
    if fornecedor is None:
        raise GroundTruthDivergente(
            f"Nenhum fornecedor ativo com id >= {ID_MINIMO_FORNECEDOR}; o fixture mudou."
        )
    return {"id_medido": fornecedor.id, "nome": fornecedor.nome}


def _preencher(valor: Any, nome_fornecedor: str) -> Any:
    """Troca o marcador pelo nome real, em frases e regras."""
    if isinstance(valor, str):
        return valor.replace(MARCADOR_FORNECEDOR, nome_fornecedor)
    if isinstance(valor, dict):
        return {chave: _preencher(v, nome_fornecedor) for chave, v in valor.items()}
    if isinstance(valor, list):
        return [_preencher(v, nome_fornecedor) for v in valor]
    return valor


def _entidade(item: dict[str, Any]) -> str:
    # Pelo id, nao pelo tipo esperado: "cupom em reais" espera esclarecimento,
    # mas a regressao dele e de cupom.
    return item["id"].split("-")[1]


def _corpo_do_item(item: dict[str, Any], fornecedor: dict[str, Any]) -> dict[str, Any]:
    """input so com o que o agente recebe; expected so com o que se confere."""
    usa_fornecedor = MARCADOR_FORNECEDOR in item["mensagem"]
    return {
        "input": {
            "mensagem": _preencher(item["mensagem"], fornecedor["nome"]),
            "hoje": DATA_REFERENCIA.isoformat(),
        },
        "expected_output": {
            "tipo": item["tipo"],
            "campos": _preencher(item["campos"], fornecedor["nome"]),
            "avisos": item["avisos"],
            "motivos": item.get("motivos"),
            "cadastravel": item["cadastravel"],
        },
        "metadata": {
            "categoria": item["categoria"],
            "entidade": _entidade(item),
            "nota_revisao": item["nota_revisao"],
            # Retrato datado: quem avalia resolve o id pelo nome de novo.
            "fornecedor_referencia": fornecedor if usa_fornecedor else None,
            "medido_em": obter_configuracao().hoje().isoformat(),
            "publicado_por": "scripts/seed_dataset.py",
        },
    }


def _conferir_cnpjs() -> None:
    # CNPJ invalido no dataset faria o item medir a validacao do schema,
    # nao o agente.
    for cnpj in (CNPJ_COMPLETO, CNPJ_SEM_CIDADE):
        if not cnpj_valido(normalizar_cnpj(cnpj)):
            raise SystemExit(f"CNPJ de teste invalido no script: {cnpj}")


def seed() -> None:
    logging.basicConfig(level=obter_configuracao().log_level)
    _conferir_cnpjs()

    cliente = obter_cliente()
    if cliente is None:
        raise SystemExit(
            "Langfuse sem credenciais configuradas. Preencha LANGFUSE_PUBLIC_KEY e "
            "LANGFUSE_SECRET_KEY no .env antes de publicar o dataset."
        )

    fornecedor = asyncio.run(_conferir_banco(ITENS))

    cliente.create_dataset(
        name=NOME_DATASET,
        description=DESCRICAO,
        metadata={
            "versao": "v0",
            "data_referencia": DATA_REFERENCIA.isoformat(),
            "fornecedor_nas_frases": fornecedor,
            "publicado_por": "scripts/seed_dataset.py",
            "publicado_em": obter_configuracao().hoje().isoformat(),
        },
    )

    for item in ITENS:
        cliente.create_dataset_item(
            dataset_name=NOME_DATASET,
            id=item["id"],
            status="ACTIVE",
            **_corpo_do_item(item, fornecedor),
        )

    cliente.flush()

    por_entidade: dict[str, int] = {}
    for item in ITENS:
        por_entidade[_entidade(item)] = por_entidade.get(_entidade(item), 0) + 1
    print(
        f"Dataset {NOME_DATASET!r} publicado: {len(ITENS)} itens {por_entidade}. "
        f"Fornecedor nas frases: {fornecedor['nome']!r} (id {fornecedor['id_medido']})."
    )


if __name__ == "__main__":
    seed()
