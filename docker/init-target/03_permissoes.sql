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