-- =====================================================================
-- Dados ficticios da loja (~13 mil linhas).
--
-- Geracao procedural via generate_series/random(), evitando as 3
-- armadilhas documentadas no CLAUDE.md:
--   1. ::int arredonda em vez de truncar -> sempre floor() antes do
--      cast num sorteio de indice.
--   2. CASE encadeado reavalia random() a cada WHEN -> o sorteio e
--      materializado numa CTE antes, cada WHEN compara contra a MESMA
--      coluna ja fixa.
--   3. CROSS JOIN LATERAL sem correlacao real e avaliado uma unica vez
--      -> todo LATERAL abaixo referencia de verdade a linha externa
--      (ex.: "WHERE enderecos.cliente_id = c.id").
--
-- Correcoes adicionais (nao obvias na primeira tentativa):
--   A. enderecos garante >=1 linha por cliente ANTES de gerar pedidos,
--      senao o CROSS JOIN LATERAL de pedidos descartaria em silencio
--      pedidos de clientes sem nenhum endereco.
--   B. itens_pedido/avaliacoes usam generate_series + INSERT ... ON
--      CONFLICT DO NOTHING, nunca "DISTINCT ON (...) ORDER BY ...
--      LIMIT n" (esse padrao teria vico sistematico: o ORDER BY pela
--      chave seguido de LIMIT corta sempre as chaves mais baixas).
-- =====================================================================

BEGIN;

SET client_encoding = 'UTF8';


-- =====================================================================
-- CATEGORIAS (25 linhas: 8 raiz + 17 subcategorias)
-- =====================================================================
INSERT INTO categorias (nome, categoria_pai_id)
SELECT nome, NULL
FROM unnest(ARRAY[
    'Eletronicos', 'Moda', 'Casa e Decoracao', 'Esporte e Lazer',
    'Beleza e Cuidados', 'Livros e Papelaria', 'Brinquedos', 'Alimentos e Bebidas'
]) AS nome;

INSERT INTO categorias (nome, categoria_pai_id)
SELECT nome, floor(random() * 8)::int + 1
FROM unnest(ARRAY[
    'Celulares e Smartphones', 'Notebooks', 'Fones de Ouvido', 'Televisores',
    'Roupas Femininas', 'Roupas Masculinas', 'Calcados', 'Acessorios de Moda',
    'Moveis', 'Utensilios de Cozinha', 'Decoracao de Interiores',
    'Suplementos', 'Equipamentos de Ginastica',
    'Maquiagem', 'Perfumes',
    'Livros de Ficcao', 'Material Escolar'
]) AS nome;


-- =====================================================================
-- FORNECEDORES (40 linhas)
-- =====================================================================
INSERT INTO fornecedores (nome, cnpj, email_contato, telefone, cidade, estado, ativo)
SELECT
    prefixos[floor(random() * array_length(prefixos, 1))::int + 1] || ' ' || g,
    lpad(g::text, 14, '0'),
    'contato' || g || '@fornecedor.com.br',
    '11' || lpad((90000000 + g)::text, 8, '0'),
    cidades[floor(random() * array_length(cidades, 1))::int + 1],
    estados[floor(random() * array_length(estados, 1))::int + 1],
    (random() > 0.05)
FROM generate_series(1, 40) AS g
CROSS JOIN (SELECT ARRAY['Comercial', 'Distribuidora', 'Industria', 'Importadora', 'Atacado', 'Grupo', 'Casa', 'Armazem'] AS prefixos) p1
CROSS JOIN (SELECT ARRAY['Sao Paulo', 'Rio de Janeiro', 'Belo Horizonte', 'Curitiba', 'Porto Alegre', 'Salvador', 'Recife', 'Fortaleza', 'Brasilia', 'Manaus'] AS cidades) p2
CROSS JOIN (SELECT ARRAY['SP', 'RJ', 'MG', 'PR', 'RS', 'BA', 'PE', 'CE', 'DF', 'AM'] AS estados) p3;


-- =====================================================================
-- PRODUTOS (500 linhas)
-- =====================================================================
INSERT INTO produtos (categoria_id, fornecedor_id, nome, sku, preco, estoque, ativo)
SELECT
    floor(random() * 25)::int + 1,
    floor(random() * 40)::int + 1,
    nomes[floor(random() * array_length(nomes, 1))::int + 1] || ' ' || g,
    'SKU-' || lpad(g::text, 6, '0'),
    round((random() * 990 + 9.9)::numeric, 2),
    floor(random() * 200)::int,
    (random() > 0.1)
FROM generate_series(1, 500) AS g
CROSS JOIN (SELECT ARRAY[
    'Smartphone', 'Notebook', 'Fone Bluetooth', 'Camiseta', 'Calca Jeans',
    'Tenis', 'Sofa', 'Panela', 'Suplemento Proteico', 'Batom', 'Perfume',
    'Livro', 'Boneco', 'Cafe Gourmet', 'Mochila', 'Relogio', 'Cadeira Gamer',
    'Micro-ondas', 'Bicicleta', 'Mala de Viagem'
] AS nomes) n;


-- =====================================================================
-- CLIENTES (1.200 linhas)
-- =====================================================================
INSERT INTO clientes (nome, email, cpf, data_nascimento, ativo)
SELECT
    primeiros[floor(random() * array_length(primeiros, 1))::int + 1] || ' ' ||
        ultimos[floor(random() * array_length(ultimos, 1))::int + 1],
    'cliente' || g || '@exemplo.com.br',
    lpad(g::text, 11, '0'),
    (DATE '1960-01-01' + floor(random() * 20000)::int),
    (random() > 0.08)
FROM generate_series(1, 1200) AS g
CROSS JOIN (SELECT ARRAY['Ana', 'Bruno', 'Carla', 'Daniel', 'Eduarda', 'Felipe', 'Gabriela', 'Hugo', 'Isabela', 'Joao', 'Karina', 'Lucas', 'Mariana', 'Nicolas', 'Olivia', 'Pedro', 'Queila', 'Rafael', 'Sabrina', 'Thiago'] AS primeiros) p
CROSS JOIN (SELECT ARRAY['Silva', 'Santos', 'Oliveira', 'Souza', 'Rodrigues', 'Ferreira', 'Alves', 'Pereira', 'Lima', 'Gomes'] AS ultimos) u;


-- =====================================================================
-- ENDERECOS (1.500 linhas em 2 passadas - Correcao A)
-- =====================================================================

-- Passada 1: exatamente 1 endereco por cliente (garante cobertura
-- total antes de qualquer LATERAL correlacionado em pedidos).
INSERT INTO enderecos (cliente_id, tipo, logradouro, numero, complemento, bairro, cidade, estado, cep, principal)
SELECT
    g,
    'entrega',
    logradouros[floor(random() * array_length(logradouros, 1))::int + 1] || ' ' || (floor(random() * 2000)::int + 1),
    (floor(random() * 2000)::int + 1)::text,
    NULL,
    bairros[floor(random() * array_length(bairros, 1))::int + 1],
    cidades[floor(random() * array_length(cidades, 1))::int + 1],
    estados[floor(random() * array_length(estados, 1))::int + 1],
    lpad((10000000 + g)::text, 8, '0'),
    TRUE
FROM generate_series(1, 1200) AS g
CROSS JOIN (SELECT ARRAY['Rua das Flores', 'Avenida Brasil', 'Rua Sete de Setembro', 'Alameda Santos', 'Rua XV de Novembro', 'Avenida Paulista', 'Rua das Palmeiras', 'Travessa da Paz'] AS logradouros) l
CROSS JOIN (SELECT ARRAY['Centro', 'Jardim America', 'Vila Nova', 'Boa Vista', 'Santa Rosa', 'Bela Vista', 'Sao Jose'] AS bairros) b
CROSS JOIN (SELECT ARRAY['Sao Paulo', 'Rio de Janeiro', 'Belo Horizonte', 'Curitiba', 'Porto Alegre', 'Salvador', 'Recife', 'Fortaleza', 'Brasilia', 'Manaus'] AS cidades) c
CROSS JOIN (SELECT ARRAY['SP', 'RJ', 'MG', 'PR', 'RS', 'BA', 'PE', 'CE', 'DF', 'AM'] AS estados) e;

-- Passada 2: 300 enderecos extras para clientes sorteados (variedade
-- de "mais de um endereco por cliente").
INSERT INTO enderecos (cliente_id, tipo, logradouro, numero, complemento, bairro, cidade, estado, cep, principal)
SELECT
    floor(random() * 1200)::int + 1,
    (CASE WHEN random() < 0.5 THEN 'entrega' ELSE 'cobranca' END),
    logradouros[floor(random() * array_length(logradouros, 1))::int + 1] || ' ' || (floor(random() * 2000)::int + 1),
    (floor(random() * 2000)::int + 1)::text,
    (CASE WHEN random() < 0.3 THEN 'Apto ' || (floor(random() * 200)::int + 1) ELSE NULL END),
    bairros[floor(random() * array_length(bairros, 1))::int + 1],
    cidades[floor(random() * array_length(cidades, 1))::int + 1],
    estados[floor(random() * array_length(estados, 1))::int + 1],
    lpad((20000000 + g)::text, 8, '0'),
    FALSE
FROM generate_series(1, 300) AS g
CROSS JOIN (SELECT ARRAY['Rua das Flores', 'Avenida Brasil', 'Rua Sete de Setembro', 'Alameda Santos', 'Rua XV de Novembro', 'Avenida Paulista', 'Rua das Palmeiras', 'Travessa da Paz'] AS logradouros) l
CROSS JOIN (SELECT ARRAY['Centro', 'Jardim America', 'Vila Nova', 'Boa Vista', 'Santa Rosa', 'Bela Vista', 'Sao Jose'] AS bairros) b
CROSS JOIN (SELECT ARRAY['Sao Paulo', 'Rio de Janeiro', 'Belo Horizonte', 'Curitiba', 'Porto Alegre', 'Salvador', 'Recife', 'Fortaleza', 'Brasilia', 'Manaus'] AS cidades) c
CROSS JOIN (SELECT ARRAY['SP', 'RJ', 'MG', 'PR', 'RS', 'BA', 'PE', 'CE', 'DF', 'AM'] AS estados) e;


-- =====================================================================
-- CUPONS (60 linhas)
-- validade_inicio materializado numa subquery antes de derivar
-- validade_fim, para garantir fim >= inicio sempre (nao sorteados
-- independentemente, o que poderia violar ck_cupons_validade_coerente).
-- =====================================================================
INSERT INTO cupons (codigo, percentual_desconto, validade_inicio, validade_fim, ativo)
SELECT
    'CUPOM' || lpad(g::text, 4, '0'),
    floor(random() * 40)::int + 5,
    inicio,
    inicio + (floor(random() * 90)::int + 10),
    (random() > 0.2)
FROM (
    SELECT g, CURRENT_DATE - floor(random() * 180)::int AS inicio
    FROM generate_series(1, 60) AS g
) sorteio;


-- =====================================================================
-- PEDIDOS (2.500 linhas)
-- cliente_id, cupom_id e o sorteio de status materializados numa CTE
-- antes do CASE (armadilha 2). endereco_entrega_id vem de um CROSS
-- JOIN LATERAL correlacionado de verdade com c.id (armadilha 3) -
-- como a Correcao A garante >=1 endereco por cliente, este LATERAL
-- nunca descarta uma linha por falta de endereco.
-- valor_total aqui e so um palpite inicial; e recalculado abaixo a
-- partir da soma real de itens_pedido, depois que eles existirem.
-- =====================================================================
WITH sorteio AS (
    SELECT
        g,
        floor(random() * 1200)::int + 1 AS cliente_id,
        random() AS r_status,
        (CASE WHEN random() < 0.35 THEN floor(random() * 60)::int + 1 ELSE NULL END) AS cupom_id
    FROM generate_series(1, 2500) AS g
)
INSERT INTO pedidos (cliente_id, endereco_entrega_id, cupom_id, status, valor_total, criado_em)
SELECT
    c.id,
    e.id,
    s.cupom_id,
    CASE
        WHEN s.r_status < 0.10 THEN 'cancelado'
        WHEN s.r_status < 0.30 THEN 'pendente'
        WHEN s.r_status < 0.60 THEN 'pago'
        WHEN s.r_status < 0.85 THEN 'enviado'
        ELSE 'entregue'
    END,
    round((random() * 800 + 20)::numeric, 2),
    NOW() - (floor(random() * 365)::text || ' days')::interval
FROM sorteio s
JOIN clientes c ON c.id = s.cliente_id
CROSS JOIN LATERAL (
    SELECT id FROM enderecos WHERE enderecos.cliente_id = c.id ORDER BY random() LIMIT 1
) e;


-- =====================================================================
-- ITENS_PEDIDO (~3.800 linhas - Correcao B)
-- generate_series gera excedente (4.500 candidatos) para o espaco de
-- 2.500 x 500 = 1,25 milhao de combinacoes; ON CONFLICT DO NOTHING
-- absorve colisoes sem viesar a distribuicao por pedido_id.
-- =====================================================================
INSERT INTO itens_pedido (pedido_id, produto_id, quantidade, preco_unitario)
SELECT
    p.pedido_id, p.produto_id, p.quantidade, pr.preco
FROM (
    SELECT
        floor(random() * 2500)::int + 1 AS pedido_id,
        floor(random() * 500)::int + 1  AS produto_id,
        floor(random() * 3)::int + 1    AS quantidade
    FROM generate_series(1, 4500)
) p
JOIN produtos pr ON pr.id = p.produto_id
ON CONFLICT ON CONSTRAINT uq_itens_pedido_pedido_produto DO NOTHING;

-- Reconcilia valor_total com a soma real dos itens gerados acima -
-- so agora essa informacao existe.
UPDATE pedidos p
SET valor_total = sub.total
FROM (
    SELECT pedido_id, SUM(quantidade * preco_unitario) AS total
    FROM itens_pedido
    GROUP BY pedido_id
) sub
WHERE p.id = sub.pedido_id;


-- =====================================================================
-- PAGAMENTOS (2.500 linhas, 1 por pedido)
-- forma_pagamento e status materializados na CTE antes dos CASE
-- (armadilha 2); valor usa o valor_total ja reconciliado do pedido.
-- =====================================================================
WITH sorteio AS (
    SELECT id AS pedido_id, random() AS r_forma, random() AS r_status
    FROM pedidos
)
INSERT INTO pagamentos (pedido_id, forma_pagamento, valor, status, criado_em)
SELECT
    s.pedido_id,
    CASE
        WHEN s.r_forma < 0.35 THEN 'cartao_credito'
        WHEN s.r_forma < 0.55 THEN 'pix'
        WHEN s.r_forma < 0.85 THEN 'cartao_debito'
        ELSE 'boleto'
    END,
    GREATEST(p.valor_total, 0.01),
    CASE
        WHEN s.r_status < 0.85 THEN 'aprovado'
        WHEN s.r_status < 0.95 THEN 'recusado'
        ELSE 'estornado'
    END,
    p.criado_em
FROM sorteio s
JOIN pedidos p ON p.id = s.pedido_id;


-- =====================================================================
-- AVALIACOES (~800 linhas - mesma tecnica da Correcao B)
-- =====================================================================
WITH sorteio AS (
    SELECT
        floor(random() * 500)::int + 1  AS produto_id,
        floor(random() * 1200)::int + 1 AS cliente_id,
        floor(random() * 5)::int + 1    AS nota_bruta,
        random() AS r_comentario
    FROM generate_series(1, 820)
)
INSERT INTO avaliacoes (produto_id, cliente_id, nota, comentario)
SELECT
    sorteio.produto_id,
    sorteio.cliente_id,
    sorteio.nota_bruta,
    CASE
        WHEN r_comentario < 0.4
            THEN comentarios[floor(random() * array_length(comentarios, 1))::int + 1]
        ELSE NULL
    END
FROM sorteio
CROSS JOIN (SELECT ARRAY[
    'Otimo produto, recomendo!', 'Chegou rapido e bem embalado.',
    'Qualidade abaixo do esperado.', 'Superou minhas expectativas.',
    'Custo-beneficio excelente.', 'Nao gostei muito.',
    'Vou comprar novamente.', 'Atendeu perfeitamente o que precisava.'
] AS comentarios) c
ON CONFLICT ON CONSTRAINT uq_avaliacoes_produto_cliente DO NOTHING;


ANALYZE categorias;
ANALYZE fornecedores;
ANALYZE produtos;
ANALYZE clientes;
ANALYZE enderecos;
ANALYZE cupons;
ANALYZE pedidos;
ANALYZE itens_pedido;
ANALYZE pagamentos;
ANALYZE avaliacoes;

COMMIT;
