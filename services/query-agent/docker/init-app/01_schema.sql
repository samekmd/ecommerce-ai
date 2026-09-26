-- =====================================================================
-- Banco da aplicacao - agente Text-to-SQL
-- Armazena metadados do banco alvo, filtros
-- de negocio reutilizaveis e logs de execucao do agente.
-- =====================================================================

SET client_encoding = 'UTF8';

-- ---------------------------------------------------------------------
-- Funcao utilitaria: atualiza automaticamente a coluna atualizado_em
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_atualizado_em()
RETURNS TRIGGER AS $$
BEGIN
    NEW.atualizado_em = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- =====================================================================
-- BANCOS
-- Bancos de dados alvo que o agente pode consultar.
-- IMPORTANTE: nao armazena credenciais. O campo chave_conexao guarda
-- o NOME da variavel de ambiente resolvida pelo config.py.
-- =====================================================================
CREATE TABLE bancos (
    id            SERIAL PRIMARY KEY,
    nome          TEXT        NOT NULL,
    chave_conexao TEXT        NOT NULL,
    descricao     TEXT,
    ativo         BOOLEAN     NOT NULL DEFAULT TRUE,
    criado_em     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_bancos_nome UNIQUE (nome),
    CONSTRAINT uq_bancos_chave_conexao UNIQUE (chave_conexao)
);

COMMENT ON COLUMN bancos.chave_conexao IS 'Nome da variavel de ambiente com a URL de conexao, ex: TARGET_DB_VENDAS';

CREATE TRIGGER trg_bancos_atualizado_em
    BEFORE UPDATE ON bancos
    FOR EACH ROW EXECUTE FUNCTION set_atualizado_em();


-- =====================================================================
-- TABELAS
-- Catalogo de tabelas do banco alvo. A coluna "descricao" e o que a
-- tool get_schema devolve: uma linha por tabela, curta o suficiente
-- para o agente decidir relevancia sem estourar o contexto.
-- =====================================================================
CREATE TABLE tabelas (
    id            SERIAL PRIMARY KEY,
    banco_id      INTEGER     NOT NULL REFERENCES bancos(id) ON DELETE CASCADE,
    nome          TEXT        NOT NULL,
    schema_name   TEXT        NOT NULL DEFAULT 'public',
    descricao     TEXT        NOT NULL,
    dominio       TEXT,
    ativo         BOOLEAN     NOT NULL DEFAULT TRUE,
    criado_em     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_tabelas_identidade UNIQUE (banco_id, schema_name, nome),
    CONSTRAINT ck_tabelas_descricao_nao_vazia CHECK (length(trim(descricao)) > 0)
);

COMMENT ON COLUMN tabelas.descricao IS 'Resumo de uma linha do proposito da tabela, consumido por get_schema';
COMMENT ON COLUMN tabelas.dominio   IS 'Area de negocio, permite filtrar get_schema quando ha muitas tabelas';

CREATE INDEX ix_tabelas_banco   ON tabelas (banco_id) WHERE ativo;
CREATE INDEX ix_tabelas_dominio ON tabelas (dominio)  WHERE ativo;

CREATE TRIGGER trg_tabelas_atualizado_em
    BEFORE UPDATE ON tabelas
    FOR EACH ROW EXECUTE FUNCTION set_atualizado_em();


-- =====================================================================
-- COLUNAS
-- Detalhe pesado, devolvido pela tool get_descriptions apenas para as
-- tabelas que o agente julgou relevantes.
-- =====================================================================
CREATE TABLE colunas (
    id              SERIAL PRIMARY KEY,
    tabela_id       INTEGER     NOT NULL REFERENCES tabelas(id) ON DELETE CASCADE,
    nome            TEXT        NOT NULL,
    tipo            TEXT        NOT NULL,
    descricao       TEXT,
    is_pk           BOOLEAN     NOT NULL DEFAULT FALSE,
    is_fk           BOOLEAN     NOT NULL DEFAULT FALSE,
    referencia      TEXT,
    valores_exemplo TEXT[],
    nullable        BOOLEAN     NOT NULL DEFAULT TRUE,
    ordem           INTEGER,
    ativo           BOOLEAN     NOT NULL DEFAULT TRUE,
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_colunas_tabela_nome UNIQUE (tabela_id, nome)
);

COMMENT ON COLUMN colunas.referencia      IS 'Quando is_fk, indica tabela.coluna referenciada';
COMMENT ON COLUMN colunas.valores_exemplo IS 'Valores possiveis de colunas categoricas, reduz erro em clausulas WHERE';
COMMENT ON COLUMN colunas.ordem           IS 'Ordem de exibicao da coluna na tabela';

CREATE INDEX ix_colunas_tabela ON colunas (tabela_id) WHERE ativo;

CREATE TRIGGER trg_colunas_atualizado_em
    BEFORE UPDATE ON colunas
    FOR EACH ROW EXECUTE FUNCTION set_atualizado_em();


-- =====================================================================
-- FILTROS
-- Regras de negocio reutilizaveis expressas em SQL. O campo
-- "quando_usar" e a instrucao que permite ao agente escolher o filtro
-- certo, sem ele a lista de filtros nao tem criterio de selecao.
-- =====================================================================
CREATE TABLE filtros (
    id            SERIAL PRIMARY KEY,
    tabela_id     INTEGER     NOT NULL REFERENCES tabelas(id) ON DELETE CASCADE,
    nome          TEXT        NOT NULL,
    descricao     TEXT        NOT NULL,
    expressao_sql TEXT        NOT NULL,
    quando_usar   TEXT        NOT NULL,
    ativo         BOOLEAN     NOT NULL DEFAULT TRUE,
    criado_em     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_filtros_tabela_nome UNIQUE (tabela_id, nome),
    CONSTRAINT ck_filtros_expressao_nao_vazia CHECK (length(trim(expressao_sql)) > 0)
);

COMMENT ON COLUMN filtros.expressao_sql IS 'Predicado SQL aplicavel em WHERE, ex: status = ''ativo'' AND deletado_em IS NULL';
COMMENT ON COLUMN filtros.quando_usar   IS 'Instrucao para o LLM sobre em que situacao aplicar este filtro';

CREATE INDEX ix_filtros_tabela ON filtros (tabela_id) WHERE ativo;

CREATE TRIGGER trg_filtros_atualizado_em
    BEFORE UPDATE ON filtros
    FOR EACH ROW EXECUTE FUNCTION set_atualizado_em();


-- =====================================================================
-- LOGS
-- Registro de cada chamada de tool feita pelo agente. Nao possui FK
-- para as demais tabelas de proposito: o log deve sobreviver a
-- alteracoes ou remocoes no catalogo de metadados.
-- =====================================================================
CREATE TABLE logs (
    id               BIGSERIAL PRIMARY KEY,
    thread_id        TEXT,
    pergunta         TEXT,
    tool_name        TEXT        NOT NULL,
    argumentos       JSONB,
    query_executada  TEXT,
    sucesso          BOOLEAN     NOT NULL DEFAULT TRUE,
    erro             TEXT,
    linhas_retornadas INTEGER,
    duracao_ms       INTEGER,
    criado_em        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON COLUMN logs.thread_id IS 'Agrupa todas as chamadas de uma mesma conversa';
COMMENT ON COLUMN logs.erro      IS 'Mensagem devolvida pelo banco quando sucesso = false';

CREATE INDEX ix_logs_thread    ON logs (thread_id, criado_em);
CREATE INDEX ix_logs_criado_em ON logs (criado_em DESC);
CREATE INDEX ix_logs_falhas    ON logs (criado_em DESC) WHERE NOT sucesso;