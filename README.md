# ecommerce-ai

Plataforma de agentes de IA para operar um e-commerce em linguagem natural: **consultar** os dados
da loja e **cadastrar** novos registros a partir de uma frase, com revisão humana antes de gravar.

---

## Objetivo

O projeto reúne dois agentes e uma interface web sobre o mesmo banco de e-commerce:

- **query-agent** (Text-to-SQL, somente leitura): recebe uma pergunta em português, descobre quais
  tabelas são relevantes a partir de um catálogo, monta e executa a consulta SQL e devolve a
  resposta interpretada. O schema do banco alvo é tratado como desconhecido em tempo de
  desenvolvimento e é descoberto em runtime.
- **ops-agent** (cadastro): recebe uma frase como *"Cadastre 5 camisas da Nike a 100 reais,
  fornecedor XYZ"* e devolve uma **proposta estruturada** que pré-preenche um formulário. O usuário
  revisa, corrige, anexa a imagem e confirma; só então o cadastro é gravado.
- **frontend**: interface web com duas abas, *Cadastro* (ops-agent) e *Consultas* (query-agent).

Dois princípios guiam o desenho:

1. **O LLM não é camada de segurança.** As proteções reais ficam fora do modelo: usuários de banco
   com permissões mínimas, validação do SQL, revalidação de todo cadastro, tetos de linhas e de tempo.
2. **O agente propõe, o humano confirma, o serviço grava.** O ops-agent nunca escreve no banco nem
   gera SQL; a gravação é um endpoint REST comum, sem LLM, que revalida tudo.

---

## Estrutura do projeto

Monorepo com um workspace [uv](https://docs.astral.sh/uv/) para os serviços Python e um app Vite
para o frontend.

```
ecommerce-ai/
├── .env.example            # .env único, compartilhado pelos dois serviços
├── pyproject.toml          # workspace uv (members = services/*)
├── docker/
│   ├── docker-compose.yml  # app_db (:5433) e target_db (:5434)
│   ├── init-app/           # catálogo do query-agent + auditoria do ops-agent
│   └── init-target/        # loja fictícia: schema, dados, roles, imagens de produto
├── frontend/               # React + Vite: abas Cadastro e Consultas
│   ├── docs/               # contratos das APIs (api-ops-agent.md, api-query-agent.md)
│   └── src/                # pages → components → hook → middlewares → axios
└── services/
    ├── query-agent/        # Text-to-SQL (LangGraph): API :8000 + Streamlit :8501
    │   ├── api/            # FastAPI (POST /perguntas, GET /health)
    │   ├── app.py, pages/  # interface Streamlit de teste + página de logs
    │   ├── scripts/        # seeds (catálogo, prompt, dataset) e experimento
    │   └── src/            # grafo, tools, services, repositories, models, database
    └── ops-agent/          # Cadastro (Pydantic AI): API :8001
        ├── scripts/        # seeds (prompt, dataset) e experimento
        ├── src/ops_agent/  # api, agente, schemas, services, repositories, models, database
        └── tests/          # unit, agente, api, evals
```

### Os dois bancos

| | `app_db` (porta 5433) | `target_db` (porta 5434) |
|---|---|---|
| Papel | metadados dos agentes | dados de negócio da loja |
| Conteúdo | catálogo e `logs` do query-agent; auditoria `ops_*` do ops-agent | e-commerce fictício: 10 tabelas, ~13 mil linhas |
| Acesso | leitura e escrita | `agente_leitura` (só `SELECT`) e `agente_escrita` (só `SELECT`/`INSERT` nas entidades de cadastro) |

### Como as partes se ligam

```
                      ┌──── /query/* ──► query-agent :8000 ──┐
frontend :5173 ─ proxy│                                       ├──► target_db / app_db
  (Vite)              └──── /ops/*   ──► ops-agent   :8001 ──┘
                                              │
                                 LLM (OpenRouter / Groq) · Langfuse (tracing e prompts)
```

Documentação detalhada de cada parte: [`frontend/README.md`](frontend/README.md),
[`services/query-agent/README.md`](services/query-agent/README.md),
[`frontend/docs/api-ops-agent.md`](frontend/docs/api-ops-agent.md) e
[`frontend/docs/api-query-agent.md`](frontend/docs/api-query-agent.md).

---

## Stack de desenvolvimento

| Camada | Tecnologia |
|---|---|
| Frontend | React 19, Vite, TypeScript (strict), axios, react-markdown + remark-gfm, CSS Modules, oxlint, npm |
| query-agent | Python 3.11–3.13, LangGraph + LangChain, OpenRouter, FastAPI + Uvicorn, Streamlit |
| ops-agent | Python 3.11–3.13, Pydantic AI, Pydantic 2, FastAPI + Uvicorn, Groq (principal) + OpenRouter (fallback) |
| Banco de dados | PostgreSQL 16 (Docker Compose), SQLAlchemy 2.0, psycopg 3 |
| Configuração | Pydantic Settings, `.env` compartilhado |
| Observabilidade e avaliação | Langfuse: tracing, system prompts versionados, datasets e experimentos |
| Ferramentas | uv (workspace), pytest, ruff, Make |

---

## Funcionalidades

### Consultas — query-agent

- Pergunta em linguagem natural → resposta interpretada, num loop ReAct em LangGraph.
- Quatro tools: `get_schema` (lista enxuta de tabelas), `get_descriptions` (colunas, tipos e
  exemplos só das tabelas escolhidas), `get_filters` (filtros de negócio) e `execute_sql`.
- Recuperação em dois estágios a partir do catálogo, para não estourar o contexto em bancos grandes.
- Erro de SQL volta ao modelo como texto, permitindo autocorreção.
- Conversa com memória por `thread_id` e orçamento de iterações por pergunta.
- Travas de segurança: validação do SQL (só `SELECT`/`WITH`, sem múltiplos statements), transação
  `READ ONLY`, usuário somente leitura, teto de linhas no cliente e timeouts em vários pontos.
- Auditoria de toda chamada de tool na tabela `logs`.
- API REST (`POST /perguntas`, `GET /health`) e interface Streamlit com página de logs.

### Cadastro — ops-agent

- Entidades: **produto, fornecedor, categoria e cupom** (uma por mensagem).
- `POST /api/v1/interpretar`: frase → proposta tipada (`produto`, `fornecedor`, `categoria`,
  `cupom`) ou pedido de esclarecimento, com avisos sobre campos incertos.
- Tools somente leitura (`listar_categorias`, `buscar_fornecedores`, `verificar_codigo_cupom`) e
  validador que rejeita IDs que não vieram das tools (defesa contra ID alucinado).
- Gravação via `POST /api/v1/{produtos,fornecedores,categorias,cupons}`, revalidando tudo.
- Apoio ao formulário: categorias com caminho hierárquico, busca de fornecedores e SKU sugerido.
- Imagem do produto obrigatória (JPEG, PNG ou WebP, até 2 MB, tipo verificado pelos *magic bytes*).
- Validação de CNPJ (dígitos verificadores), UF e cupons só percentuais.
- Idempotência por `Idempotency-Key` e identificação do usuário por `X-Usuario` (não é autenticação).
- Auditoria no `app_db` (`ops_interpretacoes`, `ops_cadastros`): permite comparar proposta ×
  confirmação como métrica de qualidade.
- Fallback automático de provedor de LLM e endpoints `/health` e `/ready`.

### Frontend

- **Aba Cadastro**: frase → modal de espera enquanto o agente interpreta → formulário
  pré-preenchido com avisos em destaque, autocomplete de fornecedor, seleção de categoria, SKU
  sugerido e prévia da imagem. Também permite cadastro manual, sem interpretar.
- **Aba Consultas**: chat com o query-agent, respostas em markdown renderizadas sem HTML bruto,
  botão de nova conversa e `thread_id` preservado ao recarregar a página.
- Erros das duas APIs normalizados num único formato (`ErroApi`) e exibidos nos campos certos.

### Observabilidade e avaliação

- Traces no Langfuse de cada pergunta/interpretação (nós, chamadas ao LLM e tools).
- System prompt de cada agente versionado no Langfuse (label `production`), trocável sem redeploy.
- Datasets de regressão e experimentos com métricas determinísticas para os dois agentes.
- Sem as chaves do Langfuse, tudo funciona normalmente com o prompt embutido no código.

---

## Manual de execução

### Pré-requisitos

- Docker e Docker Compose
- [uv](https://docs.astral.sh/uv/)
- Node.js e npm
- Chaves de API: `OPENROUTER_API_KEY` (query-agent e fallback do ops-agent) e `GROQ_API_KEY` (ops-agent)
- Opcional: chaves do Langfuse (`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`)

### 1. Configurar o ambiente

Na raiz do repositório:

```bash
cp .env.example .env
```

Preencha no `.env`, no mínimo, `OPENROUTER_API_KEY`, `GROQ_API_KEY` e `APP_DB_PASSWORD` — a mesma
senha deve aparecer dentro de `APP_DATABASE_URL`.

### 2. Subir os bancos

```bash
docker compose --env-file .env -f docker/docker-compose.yml up -d
```

O `--env-file` é necessário: sem ele o Compose procura o `.env` em `docker/` e usa os valores padrão.
Os scripts de `init-app/` e `init-target/` rodam apenas na primeira criação dos volumes; para
reaplicá-los, use `docker compose --env-file .env -f docker/docker-compose.yml down -v` e suba de novo.

### 3. Instalar as dependências Python

```bash
uv sync
```

### 4. Popular catálogo e prompts

```bash
# query-agent: descreve as 10 tabelas da loja no catálogo (obrigatório, idempotente)
cd services/query-agent
PYTHONPATH=. uv run python scripts/seed_catalogo.py

# Opcional, só com Langfuse configurado: publica o system prompt inicial de cada agente
PYTHONPATH=. uv run python scripts/seed_prompt.py
cd ../ops-agent
uv run --package ops-agent python scripts/seed_prompt.py
cd ../..
```

### 5. Subir as APIs

Em terminais separados:

```bash
cd services/query-agent && make api   # http://localhost:8000
cd services/ops-agent && make api     # http://localhost:8001 (docs em /docs)
```

Opcionalmente, a interface Streamlit de teste do query-agent:

```bash
cd services/query-agent && make run   # http://localhost:8501
```

### 6. Subir o frontend

```bash
cd frontend
cp .env.example .env
npm install
npm run dev                           # http://localhost:5173
```

O proxy do Vite encaminha `/query/*` para `:8000` e `/ops/*` para `:8001`.

### 7. Testes e qualidade

```bash
# ops-agent (precisa dos bancos de pé; sem eles, os testes de integração são pulados)
uv run --package ops-agent pytest -q

# frontend
cd frontend && npm run build && npm run lint
```

### 8. Avaliação de regressão (requer Langfuse)

```bash
# query-agent
cd services/query-agent
PYTHONPATH=. uv run python scripts/seed_dataset.py
make avaliar                          # ou: make avaliar ITENS=<id> para poupar cota

# ops-agent
cd services/ops-agent
PYTHONPATH=. uv run --package ops-agent python scripts/seed_dataset.py
PYTHONPATH=. uv run --package ops-agent python scripts/rodar_experimento.py
```

### Resolução de problemas

| Sintoma | Causa provável |
|---|---|
| `Connection refused` nas portas 5433/5434 | containers parados; suba os bancos (passo 2) |
| `password authentication failed for user "text2sql"` | o volume foi criado com outra senha; rode `docker exec text2sql_app_db psql -U text2sql -d text2sql_app -c "ALTER USER text2sql PASSWORD '<APP_DB_PASSWORD>'"` |
| `Rate limit exceeded: free-models-per-day` | cota diária de modelo `:free` do OpenRouter; troque o modelo ou aguarde |
| Interpretação lenta no ops-agent | rate limit (429) do Groq; o SDK espera e repete antes do fallback |
| Log `usando o prompt embutido no codigo` | Langfuse sem credenciais ou inalcançável; o agente segue com o prompt do código |
| Traces não aparecem no Langfuse | chaves ausentes no `.env`, ou envio em lote ainda em andamento |
