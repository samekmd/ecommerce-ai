"""Popula o catalogo do app_db com as 10 tabelas do target_db ficticio
(banco 'loja'). Necessario para get_schema/get_descriptions/get_filters
terem o que devolver.

Idempotente: pode ser rodado de novo (ex.: apos docker compose down -v
+ reseed) sem duplicar bancos/tabelas/filtros ja cadastrados.

Uso: PYTHONPATH=. uv run python scripts/seed_catalogo.py
"""

from typing import Any

from src.database.database import sessao_app
from src.logging_config import configurar_logging
from src.repositories import banco_repository, coluna_repository, filtro_repository, tabela_repository

CHAVE_CONEXAO_LOJA = "TARGET_DB_LOJA"

TABELAS: list[dict[str, Any]] = [
    {
        "nome": "categorias",
        "dominio": "catalogo",
        "descricao": "Categorias de produtos, com hierarquia opcional de categoria pai.",
        "colunas": [
            {"nome": "id", "tipo": "integer", "is_pk": True, "nullable": False, "ordem": 1},
            {"nome": "nome", "tipo": "text", "nullable": False, "ordem": 2},
            {
                "nome": "categoria_pai_id", "tipo": "integer",
                "descricao": "Referencia a propria tabela; NULL para categoria raiz",
                "is_fk": True, "referencia": "categorias.id", "nullable": True, "ordem": 3,
            },
            {"nome": "criado_em", "tipo": "timestamptz", "nullable": False, "ordem": 4},
        ],
    },
    {
        "nome": "fornecedores",
        "dominio": "catalogo",
        "descricao": "Fornecedores que abastecem os produtos vendidos na loja.",
        "colunas": [
            {"nome": "id", "tipo": "integer", "is_pk": True, "nullable": False, "ordem": 1},
            {"nome": "nome", "tipo": "text", "nullable": False, "ordem": 2},
            {"nome": "cnpj", "tipo": "text", "descricao": "Identificador fiscal, unico", "nullable": False, "ordem": 3},
            {"nome": "email_contato", "tipo": "text", "nullable": True, "ordem": 4},
            {"nome": "telefone", "tipo": "text", "nullable": True, "ordem": 5},
            {"nome": "cidade", "tipo": "text", "nullable": False, "ordem": 6},
            {
                "nome": "estado", "tipo": "text", "descricao": "Sigla de 2 letras do estado",
                "valores_exemplo": ["SP", "RJ", "MG", "RS", "PR"], "nullable": False, "ordem": 7,
            },
            {"nome": "ativo", "tipo": "boolean", "nullable": False, "ordem": 8},
            {"nome": "criado_em", "tipo": "timestamptz", "nullable": False, "ordem": 9},
        ],
    },
    {
        "nome": "produtos",
        "dominio": "catalogo",
        "descricao": "Produtos a venda, com preco, estoque e vinculo a categoria e fornecedor.",
        "colunas": [
            {"nome": "id", "tipo": "integer", "is_pk": True, "nullable": False, "ordem": 1},
            {"nome": "categoria_id", "tipo": "integer", "is_fk": True, "referencia": "categorias.id", "nullable": False, "ordem": 2},
            {"nome": "fornecedor_id", "tipo": "integer", "is_fk": True, "referencia": "fornecedores.id", "nullable": False, "ordem": 3},
            {"nome": "nome", "tipo": "text", "nullable": False, "ordem": 4},
            {"nome": "sku", "tipo": "text", "descricao": "Codigo unico interno do produto", "nullable": False, "ordem": 5},
            {"nome": "preco", "tipo": "numeric(10,2)", "nullable": False, "ordem": 6},
            {"nome": "estoque", "tipo": "integer", "descricao": "Quantidade disponivel em estoque", "nullable": False, "ordem": 7},
            {"nome": "ativo", "tipo": "boolean", "nullable": False, "ordem": 8},
            {"nome": "criado_em", "tipo": "timestamptz", "nullable": False, "ordem": 9},
        ],
    },
    {
        "nome": "clientes",
        "dominio": "clientes",
        "descricao": "Clientes cadastrados na loja, com e-mail unico e flag de conta ativa.",
        "colunas": [
            {"nome": "id", "tipo": "integer", "is_pk": True, "nullable": False, "ordem": 1},
            {"nome": "nome", "tipo": "text", "nullable": False, "ordem": 2},
            {"nome": "email", "tipo": "text", "descricao": "E-mail unico do cliente", "nullable": False, "ordem": 3},
            {"nome": "cpf", "tipo": "text", "nullable": False, "ordem": 4},
            {"nome": "data_nascimento", "tipo": "date", "nullable": True, "ordem": 5},
            {
                "nome": "ativo", "tipo": "boolean", "descricao": "Indica se a conta do cliente esta ativa",
                "valores_exemplo": ["true", "false"], "nullable": False, "ordem": 6,
            },
            {"nome": "criado_em", "tipo": "timestamptz", "nullable": False, "ordem": 7},
        ],
    },
    {
        "nome": "enderecos",
        "dominio": "clientes",
        "descricao": "Enderecos de entrega ou cobranca vinculados a um cliente.",
        "colunas": [
            {"nome": "id", "tipo": "integer", "is_pk": True, "nullable": False, "ordem": 1},
            {"nome": "cliente_id", "tipo": "integer", "is_fk": True, "referencia": "clientes.id", "nullable": False, "ordem": 2},
            {
                "nome": "tipo", "tipo": "text", "descricao": "Finalidade do endereco",
                "valores_exemplo": ["entrega", "cobranca"], "nullable": False, "ordem": 3,
            },
            {"nome": "logradouro", "tipo": "text", "nullable": False, "ordem": 4},
            {"nome": "numero", "tipo": "text", "nullable": False, "ordem": 5},
            {"nome": "complemento", "tipo": "text", "nullable": True, "ordem": 6},
            {"nome": "bairro", "tipo": "text", "nullable": False, "ordem": 7},
            {"nome": "cidade", "tipo": "text", "nullable": False, "ordem": 8},
            {
                "nome": "estado", "tipo": "text",
                "valores_exemplo": ["SP", "RJ", "MG", "RS", "PR"], "nullable": False, "ordem": 9,
            },
            {"nome": "cep", "tipo": "text", "nullable": False, "ordem": 10},
            {"nome": "principal", "tipo": "boolean", "descricao": "Indica o endereco padrao do cliente", "nullable": False, "ordem": 11},
            {"nome": "criado_em", "tipo": "timestamptz", "nullable": False, "ordem": 12},
        ],
    },
    {
        "nome": "cupons",
        "dominio": "vendas",
        "descricao": "Cupons de desconto percentual com periodo de validade.",
        "colunas": [
            {"nome": "id", "tipo": "integer", "is_pk": True, "nullable": False, "ordem": 1},
            {"nome": "codigo", "tipo": "text", "descricao": "Codigo informado pelo cliente no checkout", "nullable": False, "ordem": 2},
            {"nome": "percentual_desconto", "tipo": "numeric(5,2)", "nullable": False, "ordem": 3},
            {"nome": "validade_inicio", "tipo": "date", "nullable": False, "ordem": 4},
            {"nome": "validade_fim", "tipo": "date", "nullable": False, "ordem": 5},
            {"nome": "ativo", "tipo": "boolean", "nullable": False, "ordem": 6},
            {"nome": "criado_em", "tipo": "timestamptz", "nullable": False, "ordem": 7},
        ],
    },
    {
        "nome": "pedidos",
        "dominio": "vendas",
        "descricao": "Pedidos feitos por clientes; tabela central para juntar cliente, itens, pagamento e entrega.",
        "colunas": [
            {"nome": "id", "tipo": "integer", "is_pk": True, "nullable": False, "ordem": 1},
            {"nome": "cliente_id", "tipo": "integer", "is_fk": True, "referencia": "clientes.id", "nullable": False, "ordem": 2},
            {"nome": "endereco_entrega_id", "tipo": "integer", "is_fk": True, "referencia": "enderecos.id", "nullable": False, "ordem": 3},
            {
                "nome": "cupom_id", "tipo": "integer", "descricao": "Cupom aplicado, se houver",
                "is_fk": True, "referencia": "cupons.id", "nullable": True, "ordem": 4,
            },
            {
                "nome": "status", "tipo": "text",
                "valores_exemplo": ["pendente", "pago", "enviado", "entregue", "cancelado"],
                "nullable": False, "ordem": 5,
            },
            {"nome": "valor_total", "tipo": "numeric(10,2)", "nullable": False, "ordem": 6},
            {"nome": "criado_em", "tipo": "timestamptz", "descricao": "Data do pedido", "nullable": False, "ordem": 7},
        ],
    },
    {
        "nome": "itens_pedido",
        "dominio": "vendas",
        "descricao": "Itens de cada pedido, com quantidade e preco unitario no momento da compra.",
        "colunas": [
            {"nome": "id", "tipo": "bigint", "is_pk": True, "nullable": False, "ordem": 1},
            {"nome": "pedido_id", "tipo": "integer", "is_fk": True, "referencia": "pedidos.id", "nullable": False, "ordem": 2},
            {"nome": "produto_id", "tipo": "integer", "is_fk": True, "referencia": "produtos.id", "nullable": False, "ordem": 3},
            {"nome": "quantidade", "tipo": "integer", "nullable": False, "ordem": 4},
            {
                "nome": "preco_unitario", "tipo": "numeric(10,2)",
                "descricao": "Snapshot do preco do produto no momento da compra; nao reflete produtos.preco atual",
                "nullable": False, "ordem": 5,
            },
            {"nome": "criado_em", "tipo": "timestamptz", "nullable": False, "ordem": 6},
        ],
    },
    {
        "nome": "pagamentos",
        "dominio": "vendas",
        "descricao": "Pagamentos associados a pedidos, com forma e status da transacao.",
        "colunas": [
            {"nome": "id", "tipo": "integer", "is_pk": True, "nullable": False, "ordem": 1},
            {"nome": "pedido_id", "tipo": "integer", "is_fk": True, "referencia": "pedidos.id", "nullable": False, "ordem": 2},
            {
                "nome": "forma_pagamento", "tipo": "text",
                "valores_exemplo": ["cartao_credito", "cartao_debito", "pix", "boleto"],
                "nullable": False, "ordem": 3,
            },
            {"nome": "valor", "tipo": "numeric(10,2)", "nullable": False, "ordem": 4},
            {
                "nome": "status", "tipo": "text",
                "valores_exemplo": ["aprovado", "recusado", "estornado"], "nullable": False, "ordem": 5,
            },
            {"nome": "criado_em", "tipo": "timestamptz", "nullable": False, "ordem": 6},
        ],
    },
    {
        "nome": "avaliacoes",
        "dominio": "catalogo",
        "descricao": "Avaliacoes de clientes sobre produtos comprados, com nota de 1 a 5.",
        "colunas": [
            {"nome": "id", "tipo": "integer", "is_pk": True, "nullable": False, "ordem": 1},
            {"nome": "produto_id", "tipo": "integer", "is_fk": True, "referencia": "produtos.id", "nullable": False, "ordem": 2},
            {"nome": "cliente_id", "tipo": "integer", "is_fk": True, "referencia": "clientes.id", "nullable": False, "ordem": 3},
            {
                "nome": "nota", "tipo": "smallint", "descricao": "Nota de 1 (pior) a 5 (melhor)",
                "valores_exemplo": ["1", "2", "3", "4", "5"], "nullable": False, "ordem": 4,
            },
            {"nome": "comentario", "tipo": "text", "nullable": True, "ordem": 5},
            {"nome": "criado_em", "tipo": "timestamptz", "nullable": False, "ordem": 6},
        ],
    },
]

FILTROS: list[dict[str, str]] = [
    {
        "tabela": "pedidos",
        "nome": "pedidos_concluidos",
        "descricao": "Pedidos que chegaram ao cliente com sucesso.",
        "expressao_sql": "status = 'entregue'",
        "quando_usar": "Use quando a pergunta mencionar pedidos concluidos, finalizados ou entregues, excluindo pedidos em andamento ou cancelados.",
    },
    {
        "tabela": "clientes",
        "nome": "clientes_ativos",
        "descricao": "Contas de cliente ativas.",
        "expressao_sql": "ativo = true",
        "quando_usar": "Use quando a pergunta mencionar clientes ativos, ou pedir para excluir contas desativadas/inativas.",
    },
    {
        "tabela": "produtos",
        "nome": "produtos_disponiveis",
        "descricao": "Produtos disponiveis para compra.",
        "expressao_sql": "ativo = true AND estoque > 0",
        "quando_usar": "Use quando a pergunta pedir produtos disponiveis para compra, em estoque ou a venda, excluindo produtos inativos ou zerados.",
    },
    {
        "tabela": "pagamentos",
        "nome": "pagamentos_aprovados",
        "descricao": "Pagamentos efetivamente confirmados.",
        "expressao_sql": "status = 'aprovado'",
        "quando_usar": "Use quando a pergunta envolver receita, faturamento real ou pagamentos validos, excluindo recusados ou estornados.",
    },
    {
        "tabela": "cupons",
        "nome": "cupons_vigentes",
        "descricao": "Cupons validos hoje.",
        "expressao_sql": "ativo = true AND CURRENT_DATE BETWEEN validade_inicio AND validade_fim",
        "quando_usar": "Use quando a pergunta mencionar cupons validos, vigentes ou utilizaveis hoje.",
    },
]


def seed() -> None:
    configurar_logging()
    with sessao_app() as sessao:
        banco = banco_repository.buscar_por_chave_conexao(sessao, CHAVE_CONEXAO_LOJA)
        if banco is None:
            banco = banco_repository.criar(
                sessao,
                nome="Loja (fixture)",
                chave_conexao=CHAVE_CONEXAO_LOJA,
                descricao="E-commerce ficticio para desenvolvimento do agente Text-to-SQL",
            )

        tabelas_por_nome = {}
        for definicao in TABELAS:
            tabela = tabela_repository.buscar_por_identidade(sessao, banco.id, "public", definicao["nome"])
            if tabela is None:
                tabela = tabela_repository.criar(
                    sessao, banco.id, definicao["nome"], "public",
                    definicao["descricao"], definicao["dominio"],
                )
                coluna_repository.criar_lote(sessao, tabela.id, definicao["colunas"])
            tabelas_por_nome[definicao["nome"]] = tabela

        for definicao in FILTROS:
            tabela = tabelas_por_nome[definicao["tabela"]]
            if filtro_repository.buscar_por_nome(sessao, tabela.id, definicao["nome"]) is None:
                filtro_repository.criar(
                    sessao, tabela.id, definicao["nome"], definicao["descricao"],
                    definicao["expressao_sql"], definicao["quando_usar"],
                )

    print(f"Catalogo populado: {len(TABELAS)} tabelas, {len(FILTROS)} filtros.")


if __name__ == "__main__":
    seed()
