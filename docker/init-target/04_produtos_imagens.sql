-- =====================================================================
-- PRODUTOS_IMAGENS
-- Imagem principal do produto (1:1), gravada pelo ops-agent na mesma
-- transacao do produto. Tabela separada de produtos para que a imagem
-- nunca apareca em SELECT * nem nas amostras do query-agent (estouraria
-- o contexto do LLM). Bytes crus em BYTEA: base64 e so o formato de
-- transporte da API, ~33% maior.
-- Roda depois de 03_permissoes.sql de proposito: o REVOKE abaixo precisa
-- anular o SELECT herdado dos default privileges de agente_leitura.
-- =====================================================================

SET client_encoding = 'UTF8';

-- PK = produto_id garante no maximo uma imagem por produto (MVP).
-- CASCADE: a imagem nao faz sentido sem o produto dono.
-- Tamanho maximo fica no config do ops-agent, nao aqui, para poder mudar
-- sem migracao; o tipo real e validado pelos magic bytes no servico e o
-- CHECK de mime e so a ultima linha de defesa.
CREATE TABLE produtos_imagens (
    produto_id     INTEGER     PRIMARY KEY REFERENCES produtos(id) ON DELETE CASCADE,
    conteudo       BYTEA       NOT NULL,
    mime           TEXT        NOT NULL,
    tamanho_bytes  INTEGER     NOT NULL,
    criado_em      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_produtos_imagens_mime_valido
        CHECK (mime IN ('image/jpeg', 'image/png', 'image/webp')),
    CONSTRAINT ck_produtos_imagens_tamanho_positivo CHECK (tamanho_bytes > 0),
    CONSTRAINT ck_produtos_imagens_tamanho_coerente
        CHECK (tamanho_bytes = octet_length(conteudo))
);

COMMENT ON TABLE produtos_imagens IS 'Imagem principal do produto (1:1). Fora do catalogo do query-agent';

-- JPEG/PNG/WebP ja sao comprimidos: evita o TOAST tentar recomprimir a toa.
ALTER TABLE produtos_imagens ALTER COLUMN conteudo SET STORAGE EXTERNAL;

-- A imagem nunca deve chegar ao LLM do text2sql, que executa SQL gerado
-- pelo modelo como agente_leitura.
REVOKE ALL ON produtos_imagens FROM agente_leitura;

-- Gravada pelos services junto com o produto. Sem sequence: a PK e o
-- produto_id.
GRANT SELECT, INSERT ON produtos_imagens TO agente_escrita;
