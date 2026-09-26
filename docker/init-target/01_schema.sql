-- =====================================================================
-- Banco alvo ficticio - loja de e-commerce
-- Dados de negocio ficticios consultados apenas via SQL cru pelo
-- agente. Sem atualizado_em/trigger: e um banco populado uma unica vez
-- por 02_dados.sql, nunca atualizado em producao por nenhum processo.
-- =====================================================================

SET client_encoding = 'UTF8';


-- =====================================================================
-- CATEGORIAS
-- Categorias de produtos, com hierarquia opcional de uma categoria pai
-- (auto-referencia). Usada para agrupar produtos por segmento.
-- =====================================================================
CREATE TABLE categorias (
    id                SERIAL      PRIMARY KEY,
    nome              TEXT        NOT NULL,
    categoria_pai_id  INTEGER     REFERENCES categorias(id) ON DELETE SET NULL,
    criado_em         TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_categorias_nome UNIQUE (nome),
    CONSTRAINT ck_categorias_pai_diferente_de_si
        CHECK (categoria_pai_id IS NULL OR categoria_pai_id <> id)
);

CREATE INDEX ix_categorias_categoria_pai
    ON categorias (categoria_pai_id)
    WHERE categoria_pai_id IS NOT NULL;


-- =====================================================================
-- FORNECEDORES
-- Empresas que abastecem o catalogo de produtos. Entidade independente.
-- =====================================================================
CREATE TABLE fornecedores (
    id             SERIAL      PRIMARY KEY,
    nome           TEXT        NOT NULL,
    cnpj           TEXT        NOT NULL,
    email_contato  TEXT,
    telefone       TEXT,
    cidade         TEXT        NOT NULL,
    estado         TEXT        NOT NULL,
    ativo          BOOLEAN     NOT NULL DEFAULT TRUE,
    criado_em      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_fornecedores_cnpj UNIQUE (cnpj),
    CONSTRAINT ck_fornecedores_estado_sigla CHECK (char_length(estado) = 2)
);

CREATE INDEX ix_fornecedores_ativo ON fornecedores (ativo) WHERE ativo;


-- =====================================================================
-- PRODUTOS
-- Produtos a venda. Referencia categoria e fornecedor; RESTRICT em
-- ambos porque nenhum processo deste banco apaga categoria/fornecedor
-- com produtos vinculados - preferimos falhar alto a apagar em cascata
-- um catalogo inteiro por engano.
-- =====================================================================
CREATE TABLE produtos (
    id             SERIAL         PRIMARY KEY,
    categoria_id   INTEGER        NOT NULL REFERENCES categorias(id) ON DELETE RESTRICT,
    fornecedor_id  INTEGER        NOT NULL REFERENCES fornecedores(id) ON DELETE RESTRICT,
    nome           TEXT           NOT NULL,
    sku            TEXT           NOT NULL,
    preco          NUMERIC(10,2)  NOT NULL,
    estoque        INTEGER        NOT NULL DEFAULT 0,
    ativo          BOOLEAN        NOT NULL DEFAULT TRUE,
    criado_em      TIMESTAMPTZ    NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_produtos_sku UNIQUE (sku),
    CONSTRAINT ck_produtos_preco_positivo CHECK (preco > 0),
    CONSTRAINT ck_produtos_estoque_nao_negativo CHECK (estoque >= 0)
);

COMMENT ON TABLE produtos IS 'Catalogo de produtos a venda na loja';

CREATE INDEX ix_produtos_categoria  ON produtos (categoria_id);
CREATE INDEX ix_produtos_fornecedor ON produtos (fornecedor_id);
CREATE INDEX ix_produtos_ativo      ON produtos (ativo) WHERE ativo;


-- =====================================================================
-- CLIENTES
-- Clientes da loja. Entidade independente; email e cpf sao unicos.
-- =====================================================================
CREATE TABLE clientes (
    id                SERIAL      PRIMARY KEY,
    nome              TEXT        NOT NULL,
    email             TEXT        NOT NULL,
    cpf               TEXT        NOT NULL,
    data_nascimento   DATE,
    ativo             BOOLEAN     NOT NULL DEFAULT TRUE,
    criado_em         TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_clientes_email UNIQUE (email),
    CONSTRAINT uq_clientes_cpf UNIQUE (cpf),
    CONSTRAINT ck_clientes_cpf_formato CHECK (char_length(cpf) = 11)
);

COMMENT ON COLUMN clientes.ativo IS 'Conta ativa; usado como filtro de negocio em queries de clientes validos';

CREATE INDEX ix_clientes_ativo ON clientes (ativo) WHERE ativo;


-- =====================================================================
-- ENDERECOS
-- Enderecos de entrega ou cobranca de um cliente. CASCADE porque um
-- endereco nao faz sentido sem o cliente dono.
-- =====================================================================
CREATE TABLE enderecos (
    id            SERIAL      PRIMARY KEY,
    cliente_id    INTEGER     NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
    tipo          TEXT        NOT NULL,
    logradouro    TEXT        NOT NULL,
    numero        TEXT        NOT NULL,
    complemento   TEXT,
    bairro        TEXT        NOT NULL,
    cidade        TEXT        NOT NULL,
    estado        TEXT        NOT NULL,
    cep           TEXT        NOT NULL,
    principal     BOOLEAN     NOT NULL DEFAULT FALSE,
    criado_em     TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_enderecos_tipo_valido CHECK (tipo IN ('entrega', 'cobranca')),
    CONSTRAINT ck_enderecos_estado_sigla CHECK (char_length(estado) = 2),
    CONSTRAINT ck_enderecos_cep_formato CHECK (cep ~ '^[0-9]{8}$')
);

CREATE INDEX ix_enderecos_cliente ON enderecos (cliente_id);


-- =====================================================================
-- CUPONS
-- Cupons de desconto percentual, com periodo de validade.
-- =====================================================================
CREATE TABLE cupons (
    id                    SERIAL        PRIMARY KEY,
    codigo                TEXT          NOT NULL,
    percentual_desconto   NUMERIC(5,2)  NOT NULL,
    validade_inicio       DATE          NOT NULL,
    validade_fim          DATE          NOT NULL,
    ativo                 BOOLEAN       NOT NULL DEFAULT TRUE,
    criado_em             TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_cupons_codigo UNIQUE (codigo),
    CONSTRAINT ck_cupons_percentual_valido
        CHECK (percentual_desconto > 0 AND percentual_desconto <= 100),
    CONSTRAINT ck_cupons_validade_coerente CHECK (validade_fim >= validade_inicio)
);

CREATE INDEX ix_cupons_ativo ON cupons (ativo) WHERE ativo;


-- =====================================================================
-- PEDIDOS
-- Pedido feito por um cliente. Tabela central de join: liga cliente,
-- endereco de entrega, cupom (opcional), itens, pagamentos.
-- RESTRICT em cliente/endereco: historico de pedidos nao pode ser
-- apagado em cascata por um DELETE em clientes ou enderecos.
-- =====================================================================
CREATE TABLE pedidos (
    id                    SERIAL         PRIMARY KEY,
    cliente_id            INTEGER        NOT NULL REFERENCES clientes(id) ON DELETE RESTRICT,
    endereco_entrega_id   INTEGER        NOT NULL REFERENCES enderecos(id) ON DELETE RESTRICT,
    cupom_id              INTEGER        REFERENCES cupons(id) ON DELETE SET NULL,
    status                TEXT           NOT NULL DEFAULT 'pendente',
    valor_total           NUMERIC(10,2)  NOT NULL,
    criado_em             TIMESTAMPTZ    NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_pedidos_status_valido
        CHECK (status IN ('pendente', 'pago', 'enviado', 'entregue', 'cancelado')),
    CONSTRAINT ck_pedidos_valor_total_nao_negativo CHECK (valor_total >= 0)
);

COMMENT ON COLUMN pedidos.status IS 'pendente|pago|enviado|entregue|cancelado';

CREATE INDEX ix_pedidos_cliente   ON pedidos (cliente_id);
CREATE INDEX ix_pedidos_status    ON pedidos (status);
CREATE INDEX ix_pedidos_cupom     ON pedidos (cupom_id) WHERE cupom_id IS NOT NULL;
CREATE INDEX ix_pedidos_criado_em ON pedidos (criado_em DESC);


-- =====================================================================
-- ITENS_PEDIDO
-- Linha de pedido. preco_unitario e um SNAPSHOT do preco do produto no
-- momento da compra - nao referencia produtos.preco. Decisao de
-- modelagem real de e-commerce: se o produto mudar de preco depois, o
-- valor historico do pedido nao pode mudar retroativamente. Maior
-- volume esperado do banco -> unica tabela em BIGSERIAL.
-- =====================================================================
CREATE TABLE itens_pedido (
    id              BIGSERIAL      PRIMARY KEY,
    pedido_id       INTEGER        NOT NULL REFERENCES pedidos(id) ON DELETE CASCADE,
    produto_id      INTEGER        NOT NULL REFERENCES produtos(id) ON DELETE RESTRICT,
    quantidade      INTEGER        NOT NULL,
    preco_unitario  NUMERIC(10,2)  NOT NULL,
    criado_em       TIMESTAMPTZ    NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_itens_pedido_pedido_produto UNIQUE (pedido_id, produto_id),
    CONSTRAINT ck_itens_pedido_quantidade_positiva CHECK (quantidade > 0),
    CONSTRAINT ck_itens_pedido_preco_unitario_positivo CHECK (preco_unitario > 0)
);

COMMENT ON TABLE itens_pedido IS 'Linha de pedido; preco_unitario e o preco no momento da compra, nunca o preco atual do produto';
COMMENT ON COLUMN itens_pedido.preco_unitario IS 'Snapshot: nao recalcular a partir de produtos.preco';

CREATE INDEX ix_itens_pedido_pedido  ON itens_pedido (pedido_id);
CREATE INDEX ix_itens_pedido_produto ON itens_pedido (produto_id);


-- =====================================================================
-- PAGAMENTOS
-- Pagamento associado a um pedido. CASCADE: pagamento nao existe sem o
-- pedido.
-- =====================================================================
CREATE TABLE pagamentos (
    id               SERIAL         PRIMARY KEY,
    pedido_id        INTEGER        NOT NULL REFERENCES pedidos(id) ON DELETE CASCADE,
    forma_pagamento  TEXT           NOT NULL,
    valor            NUMERIC(10,2)  NOT NULL,
    status           TEXT           NOT NULL DEFAULT 'aprovado',
    criado_em        TIMESTAMPTZ    NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_pagamentos_forma_valida
        CHECK (forma_pagamento IN ('cartao_credito', 'cartao_debito', 'pix', 'boleto')),
    CONSTRAINT ck_pagamentos_status_valido
        CHECK (status IN ('aprovado', 'recusado', 'estornado')),
    CONSTRAINT ck_pagamentos_valor_positivo CHECK (valor > 0)
);

CREATE INDEX ix_pagamentos_pedido ON pagamentos (pedido_id);
CREATE INDEX ix_pagamentos_status ON pagamentos (status);


-- =====================================================================
-- AVALIACOES
-- Avaliacao de um cliente sobre um produto comprado. CASCADE em ambos:
-- e uma opiniao, sem valor historico/financeiro a preservar (ao
-- contrario de itens_pedido).
-- =====================================================================
CREATE TABLE avaliacoes (
    id           SERIAL      PRIMARY KEY,
    produto_id   INTEGER     NOT NULL REFERENCES produtos(id) ON DELETE CASCADE,
    cliente_id   INTEGER     NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
    nota         SMALLINT    NOT NULL,
    comentario   TEXT,
    criado_em    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_avaliacoes_produto_cliente UNIQUE (produto_id, cliente_id),
    CONSTRAINT ck_avaliacoes_nota_valida CHECK (nota BETWEEN 1 AND 5)
);

CREATE INDEX ix_avaliacoes_produto ON avaliacoes (produto_id);
CREATE INDEX ix_avaliacoes_cliente ON avaliacoes (cliente_id);
