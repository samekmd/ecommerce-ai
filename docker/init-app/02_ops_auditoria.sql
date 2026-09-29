-- =====================================================================
-- Auditoria do ops-agent
-- Frase, proposta do agente, payload confirmado no formulario e
-- resultado da gravacao. A diferenca proposta x confirmacao e a metrica
-- de qualidade do agente. Prefixo ops_: o app_db e compartilhado com o
-- query-agent, que nao le estas tabelas.
-- =====================================================================

SET client_encoding = 'UTF8';

CREATE TABLE ops_interpretacoes (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario     TEXT        NOT NULL,
    mensagem    TEXT        NOT NULL,
    modelo      TEXT        NOT NULL,
    tipo        TEXT,
    proposta    JSONB,
    -- Categoria do erro (ex.: retries_esgotados), nunca a mensagem da excecao.
    erro        TEXT,
    duracao_ms  INTEGER     NOT NULL,
    -- Liga a auditoria ao trace no Langfuse e permite medir a qualidade
    -- por versao de prompt. Nulos com tracing desligado ou prompt fallback.
    trace_id       TEXT,
    prompt_versao  INTEGER,
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Ou o agente propos (tipo), ou falhou (erro); nunca os dois.
    CONSTRAINT ck_ops_interpretacoes_resultado CHECK ((tipo IS NULL) <> (erro IS NULL))
);

CREATE INDEX ix_ops_interpretacoes_criado_em ON ops_interpretacoes (criado_em DESC);


CREATE TABLE ops_cadastros (
    id                  BIGSERIAL   PRIMARY KEY,
    interpretacao_id    UUID        REFERENCES ops_interpretacoes(id) ON DELETE SET NULL,
    usuario             TEXT        NOT NULL,
    entidade            TEXT        NOT NULL,
    -- Imagem so como {mime, tamanho_bytes}: bytes nunca entram na auditoria.
    payload             JSONB       NOT NULL,
    resultado           TEXT        NOT NULL,
    entidade_id         INTEGER,
    campo_erro          TEXT,
    chave_idempotencia  TEXT,
    -- XCriado devolvido, reenviado quando a mesma Idempotency-Key se repete.
    resposta            JSONB,
    criado_em           TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_ops_cadastros_entidade
        CHECK (entidade IN ('produto', 'fornecedor', 'categoria', 'cupom')),
    CONSTRAINT ck_ops_cadastros_resultado
        CHECK (resultado IN ('criado', 'conflito', 'invalido', 'erro'))
);

-- So cadastro bem-sucedido reserva a chave: tentativa com erro pode ser
-- repetida com a mesma chave depois de corrigida.
CREATE UNIQUE INDEX uq_ops_cadastros_idempotencia
    ON ops_cadastros (usuario, chave_idempotencia)
    WHERE chave_idempotencia IS NOT NULL AND resultado = 'criado';

CREATE INDEX ix_ops_cadastros_interpretacao
    ON ops_cadastros (interpretacao_id)
    WHERE interpretacao_id IS NOT NULL;
