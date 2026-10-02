-- =====================================================================
-- Usuario somente leitura usado pelo agente
-- Esta e a camada real de seguranca. A restricao no prompt do agente
-- (apenas SELECT) e conveniencia, nao protecao.
-- =====================================================================

CREATE ROLE agente_leitura WITH LOGIN PASSWORD 'leitura_ficticia';

-- Impede criacao de objetos no schema
REVOKE CREATE ON SCHEMA public FROM agente_leitura;

GRANT CONNECT ON DATABASE loja TO agente_leitura;
GRANT USAGE   ON SCHEMA public TO agente_leitura;

-- Leitura em tudo que ja existe
GRANT SELECT ON ALL TABLES IN SCHEMA public TO agente_leitura;

-- Leitura em tabelas criadas futuramente
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO agente_leitura;

-- Limita o tempo maximo de uma query deste usuario
ALTER ROLE agente_leitura SET statement_timeout = '30s';
ALTER ROLE agente_leitura SET idle_in_transaction_session_timeout = '60s';

-- =====================================================================
-- Usuario de escrita usado pelos services do ops-agent
-- So cadastra: SELECT/INSERT nas tabelas do MVP, sem UPDATE nem DELETE.
-- Sem default privileges de proposito: tabela nova so e gravavel com
-- grant explicito (produtos_imagens recebe o seu em 04).
-- =====================================================================

CREATE ROLE agente_escrita WITH LOGIN PASSWORD 'escrita_ficticia';

REVOKE CREATE ON SCHEMA public FROM agente_escrita;

GRANT CONNECT ON DATABASE loja TO agente_escrita;
GRANT USAGE   ON SCHEMA public TO agente_escrita;

GRANT SELECT, INSERT ON produtos, fornecedores, categorias, cupons TO agente_escrita;

-- nextval dos SERIAL
GRANT USAGE ON SEQUENCE
    produtos_id_seq, fornecedores_id_seq, categorias_id_seq, cupons_id_seq
    TO agente_escrita;

-- Transacao de cadastro e curta; passar disso e bug, nao carga.
ALTER ROLE agente_escrita SET statement_timeout = '10s';
ALTER ROLE agente_escrita SET idle_in_transaction_session_timeout = '15s';
