# Agente Text-to-SQL

Pergunta em linguagem natural → SQL → resposta interpretada, sobre um banco de dados cujo schema o agente não conhece de antemão.

---

## Objetivo do projeto

O agente recebe uma pergunta em português, descobre quais tabelas do banco alvo são relevantes, monta a consulta SQL, executa em modo somente leitura e interpreta o resultado de volta em linguagem natural.

O problema central é que **o schema do banco alvo é arbitrário e desconhecido em tempo de desenvolvimento** — ele pertence ao cliente, não ao projeto. Daí duas decisões que moldam tudo o resto:

**O schema é descoberto em runtime, a partir de um catálogo.** O agente não tem modelos declarativos das tabelas do cliente. Ele consulta um catálogo (tabelas, colunas, valores de exemplo, filtros de negócio) mantido no banco da própria aplicação. A descoberta é em dois estágios — uma lista enxuta primeiro, o detalhe pesado só das tabelas escolhidas — para que o contexto não estoure em bancos grandes.

**O LLM não é camada de segurança.** O prompt pede apenas `SELECT`, mas um modelo pode ser induzido a ignorar instrução. As proteções reais ficam fora do modelo: usuário de banco somente leitura, validação do SQL antes de qualquer ida ao servidor, teto de linhas no cliente e tetos de tempo em quatro pontos distintos.

Escopo atual: ferramenta de teste exploratório, com interface Streamlit, um usuário por vez e sem autenticação.

---

## Arquitetura do sistema

### Os dois bancos

A distinção mais importante do projeto. Confundi-los é a origem da maioria dos erros de design aqui.

| | `app_db` | `target_db` |
|---|---|---|
| Papel | metadados do agente | dados de negócio |
| Schema | conhecido, nosso | arbitrário, do cliente |
| Queries | escritas por nós | geradas pelo LLM |
| Acesso | leitura e escrita | somente leitura |
| Confiança | total | nenhuma |
| Abordagem | ORM (`src/models/`) | `text()` cru com guardrails |
| Conexão | `Session` do SQLAlchemy | `Connection` crua, sempre em rollback |
| Porta (dev) | 5433 | 5434 |

O `app_db` tem 5 tabelas: `bancos`, `tabelas`, `colunas`, `filtros` e `logs`. O prompt de sistema não fica aqui — ele é versionado no Langfuse. A fixture local do `target_db` é uma loja de e-commerce fictícia com 10 tabelas e 13.635 linhas.

### O loop do agente

Agente único em LangGraph, num loop ReAct de três peças:

```
              ┌──────────┐
  START ─────▶│  agente  │──────▶ rotear ──────▶ END
              └──────────┘           │
                    ▲                │
                    │                ▼
                    │          ┌──────────┐
                    └──────────│  tools   │
                               └──────────┘
```

- **`agente`** (`src/graph.py`) busca o prompt de sistema vigente no Langfuse (`src/prompts.py`) e chama o LLM com o histórico.
- **`tools`** é o `ToolNode` do LangGraph, com as quatro tools registradas em `src/tools/registro.py`.
- **`rotear`** (`src/routing.py`) decide entre chamar tool ou encerrar: vai para `tools` quando a última mensagem tem `tool_calls` pendentes e o orçamento de iterações não estourou.

O orçamento (`max_iteracoes`, 10 por padrão) vale **por pergunta**, não pela conversa inteira — ele reinicia a cada nova `HumanMessage`. Erro de SQL não interrompe o loop: ele volta ao modelo como texto para autocorreção.

### As quatro tools

| Tool | Devolve |
|---|---|
| `get_schema` | lista enxuta: nome e descrição de uma linha por tabela |
| `get_descriptions` | detalhe das tabelas pedidas: colunas, tipos, valores de exemplo |
| `get_filters` | filtros de negócio aplicáveis, com instrução de quando usar |
| `execute_sql` | resultado da consulta, ou a mensagem de erro do Postgres como texto |

A separação entre `get_schema` e `get_descriptions` é a recuperação em dois estágios. Se `get_schema` crescer para incluir colunas, o padrão perde o sentido.

### Direção de dependência

```
tools → services → repositories → models → database → config
```

Nunca se inverte. Em particular: `database/` contém apenas conexão e sessão, nenhuma query; repositories **recebem** a sessão como parâmetro e nunca a criam, porque quem controla a transação é a tool; e `config.py` é o único módulo que toca em `os.getenv` ou `.env`.

Duas preocupações transversais ficam fora dessa linha, e podem ser importadas de qualquer camada: `src/log_stdout.py` (log de stdout) e `src/observability/` (tracing).

```
src/
├── config.py            # única fonte de verdade de configuração
├── graph.py             # grafo: nó do agente + ToolNode
├── llm.py               # factory do LLM + teto de tempo da chamada
├── routing.py           # decide entre chamar tool ou finalizar
├── state.py             # estado do agente: histórico + orçamento
├── log_stdout.py        # decorator e helpers de log de stdout
├── prompts.py           # prompt de sistema, buscado no Langfuse
│
├── database/
│   ├── database.py      # engine e sessão do app_db
│   ├── registry.py      # cache de engines dos bancos alvo
│   └── executor.py      # única porta de entrada de SQL do LLM
│
├── models/              # 5 entidades declarativas do app_db
├── repositories/        # queries sobre os modelos
├── services/            # regra de negócio, montagem de contexto
├── tools/               # as quatro tools expostas ao agente
└── observability/       # tracing no Langfuse (setup, tracing, tags)
```

### Travas de segurança

Quatro camadas independentes entre o texto gerado pelo modelo e o banco do cliente:

1. **`executor.validar_sql()`** — antes de qualquer ida ao servidor. Aceita só `SELECT`/`WITH`, rejeita `;` fora de literal (o SQLAlchemy executaria `SELECT 1; DROP TABLE x` como chamada única e devolveria só o último resultado) e bloqueia comandos proibidos. Comentários e literais são removidos antes da análise, senão `WHERE mensagem LIKE '%DELETE%'` — consulta legítima — seria rejeitada.
2. **Transação `READ ONLY`**, marcada em `registry.conexao_leitura()`.
3. **Usuário `agente_leitura`**, com permissão apenas de `SELECT`. É a proteção real.
4. **Teto de linhas no cliente** (`max_linhas_retorno`), aplicado com `fetchmany(limite + 1)` para saber se houve corte sem carregar o resultado inteiro.

Credenciais nunca ficam no banco: a coluna `bancos.chave_conexao` guarda o **nome** da variável de ambiente (`TARGET_DB_LOJA`), nunca a URL, e o formato é validado contra `^TARGET_DB_[A-Z0-9_]+$` antes de tocar no ambiente — sem isso um registro apontando para `OPENROUTER_API_KEY` vazaria o segredo dentro de uma string de conexão.

### Travas de tempo

Uma consulta pode travar em pontos que o `statement_timeout` não alcança, porque ele só começa a contar depois que o servidor recebe a query:

| Onde | Trava |
|---|---|
| Espera por vaga no pool | `pool_timeout` de 5s (sem isso, 30s de bloqueio silencioso) |
| Rede morrendo durante a query | `tcp_user_timeout` + keepalives |
| Query lenta no servidor | `statement_timeout` de 20s → volta como texto, o agente reescreve |
| Resposta que nunca chega | teto do cliente numa thread separada, que cancela via `cancel_safe()` do psycopg e devolve a vaga ao pool |
| Chamada ao LLM travada | `invocar_com_timeout()`, com teto próprio |

Falhas são classificadas por `sqlstate`: resposta do servidor sempre traz um, falha de conexão nunca. Erro de SQL vira texto, para o agente corrigir; falha de infraestrutura levanta `FalhaDeInfraestrutura`, porque reescrever a query não resolve pool esgotado nem conexão morta.

### Observabilidade

Três registros distintos, com propósitos diferentes:

| Registro | Onde | Para quê |
|---|---|---|
| Log de stdout | `src/log_stdout.py` | acompanhar a execução ao vivo no terminal: ciclo de vida das conexões, pid do backend, query iniciada/concluída |
| Tabela `logs` | `app_db`, via `log_service` | auditoria de negócio: toda chamada de tool, com SQL, duração, linhas, sucesso e número da tentativa |
| Tracing | `src/observability/`, Langfuse | árvore completa da pergunta (nó, LLM, tools), agrupada por conversa via `session_id` |

O Langfuse também versiona o **prompt de sistema**: `src/prompts.py` busca a versão com o label `production`, e trocar de versão é mover esse label na interface — sem redeploy. O SDK mantém um cache com TTL de 60s, e o texto no repositório serve como semente e como último recurso se o Langfuse estiver inalcançável.

O `thread_id` da conversa é usado como `session_id` no Langfuse, o que agrupa todas as perguntas de uma mesma conversa. O span de `execute_sql` é enriquecido com tentativa, linhas, truncado e duração, e recebe `level=ERROR` quando a consulta falha.

### Avaliação de regressão

Mover o label `production` para outra versão do prompt, ou trocar de modelo, muda o comportamento do agente sem mudar uma linha de código. O dataset de regressão existe para responder se essa mudança quebrou algo.

**O dataset** (`scripts/seed_dataset.py`, publicado como `agente-sql-regressao-v0`) tem 9 itens em quatro categorias: contagem simples, ambiguidade de filtro de negócio, agregação com join e segurança. Cinco vêm de traces reais e carregam o `sourceTraceId`, então dá para abrir a conversa original a partir do item no Langfuse.

**O ground truth é medido contra o banco, não escrito de memória.** A fixture do `target_db` usa `random()` sem `setseed`, então parte dos valores muda a cada `docker compose down -v`. Os dois casos recebem tratamento diferente:

- **Estável** (cardinalidade fixa na fixture): o valor esperado é conferido contra o banco antes de publicar, e divergência **aborta** o seed com `GroundTruthDivergente`. Fixture que mudou pede revisão humana, não sobrescrita silenciosa.
- **Volátil**: o valor não entra no `expectedOutput`, que fica só com critérios. A verdade é o `metadata.sql_referencia` reexecutado no momento da avaliação, não o literal gravado no dataset.

**As métricas** (`scripts/rodar_experimento.py`) são determinísticas, sem juiz LLM. Três delas leem a tabela `logs` pelo `thread_id` do item; a primeira reexecuta o SQL de referência contra o banco alvo:

| Métrica | Mede | Escala |
|---|---|---|
| `bate_com_sql_referencia` | o valor do `sql_referencia`, medido na hora, aparece na resposta | 0–1, 1 é o melhor |
| `sem_tentativa_de_escrita` | nenhum `execute_sql` trouxe verbo de escrita, mesmo rejeitado | 0–1, 1 é o melhor |
| `trajetoria` | chamou `get_schema` antes do primeiro `execute_sql`, e `get_filters` onde havia filtro esperado | 0–1, 1 é o melhor |
| `custo_tentativas_execute_sql` | quantas queries foram necessárias | **contagem, menor é melhor** |

A última não é razão, e o prefixo `custo_` existe para que ela não seja lida como qualidade na mesma coluna da interface. É a leitura combinada que interessa: se ela subir enquanto `bate_com_sql_referencia` continua em 1.0, o plano piorou sem a resposta mudar — a regressão que nenhuma das outras três pega.

No nível do run saem duas agregações: `medias_por_avaliador`, e `acerto_por_categoria`, que separa regressão de contagem simples de regressão de agregação.

Fora de cobertura: os critérios subjetivos dos itens ("apresenta o valor como moeda", "recusa sem moralizar"). Medi-los exigiria juiz LLM; hoje são revisão humana.

### Interface

- **`app.py`** — chat com resposta em streaming e as tool calls visíveis em blocos colapsáveis, cada uma mostrando os argumentos e o resultado.
- **`pages/logs.py`** — visualização da tabela `logs`, somente leitura, com filtros por tool, só falhas, `thread_id` e busca textual.

---

## Stack de desenvolvimento

| Camada | Tecnologia |
|---|---|
| Linguagem | Python 3.11–3.13 |
| Gerenciador de pacotes | uv |
| Orquestração do agente | LangGraph (`StateGraph`, `ToolNode`, `InMemorySaver`) |
| Camada de LLM | LangChain, via `init_chat_model` |
| Provedor de LLM | OpenRouter (`langchain-openrouter`) |
| Banco de dados | PostgreSQL 16 (alpine) |
| ORM e driver | SQLAlchemy 2.0 + psycopg 3 |
| Configuração | Pydantic Settings |
| Interface | Streamlit (multipage) |
| Tracing | Langfuse 4 |
| Avaliação | Langfuse Datasets e Experiments |
| Ambiente local | Docker Compose |

O provedor de LLM é trocável pela configuração: os campos da Groq seguem em `config.py` como dormant, para reverter a migração se necessário.

---

## Tutorial de execução

### Pré-requisitos

- Docker e Docker Compose
- [uv](https://docs.astral.sh/uv/)
- Uma chave de API do OpenRouter (há modelos gratuitos, sujeitos a cota diária)

### 1. Configurar o ambiente

```bash
cp .env.example .env
```

Edite o `.env` e preencha, no mínimo:

- `OPENROUTER_API_KEY` — sua chave
- `APP_DB_PASSWORD` e a senha dentro de `APP_DATABASE_URL` — devem ser a mesma

As chaves do Langfuse são opcionais: sem elas o tracing fica desligado e a aplicação roda normalmente.

### 2. Subir os bancos

```bash
cd docker && docker compose up -d
```

Sobem dois containers: `app_db` na porta 5433 (catálogo vazio) e `target_db` na 5434 (a loja fictícia, já populada). Os scripts de `init-app/` e `init-target/` rodam **apenas na primeira criação do volume** — para reaplicá-los, use `docker compose down -v` e suba de novo.

### 3. Instalar as dependências

```bash
uv sync
```

### 4. Popular o prompt e o catálogo

```bash
PYTHONPATH=. uv run python scripts/seed_prompt.py
PYTHONPATH=. uv run python scripts/seed_catalogo.py
```

O `PYTHONPATH=.` é necessário: ao executar um arquivo dentro de `scripts/`, o Python coloca `scripts/` no início do `sys.path`, não a raiz do projeto, e o `import src...` falha sem ele.

O primeiro publica a versão inicial do prompt de sistema no Langfuse, com o label `production`, a partir do texto em `src/prompts.py`; a partir daí o prompt é editado pela interface do Langfuse. Ele exige as chaves do Langfuse configuradas — sem elas, o agente usa o texto embutido no código e este passo é dispensável. O segundo descreve as 10 tabelas da loja fictícia no catálogo, e é idempotente.

### 5. Rodar a aplicação

```bash
make run          # equivale a: uv run streamlit run app.py
```

Abra `http://localhost:8501`, escolha o banco alvo na barra lateral ("Loja (fixture)") e pergunte algo, por exemplo:

- *Quantos clientes existem na base?*
- *Quais são os meus 3 produtos mais bem avaliados?*
- *Qual o meu produto menos vendido?*

### 6. Inspecionar o que aconteceu

- **No terminal** onde o Streamlit roda: ciclo de vida das conexões, pid do backend e cada query iniciada/concluída.
- **Na página `logs`** da barra lateral: histórico de todas as chamadas de tool, com filtros.
- **No Langfuse**, se configurado: a árvore completa da pergunta. O envio é em lote, então o trace aparece alguns segundos depois.

### 7. Avaliar regressões

Uma vez por projeto Langfuse, publique o dataset de regressão:

```bash
PYTHONPATH=. uv run python scripts/seed_dataset.py
```

Diferente da aplicação, este passo **exige** as chaves do Langfuse. Ele é idempotente: os itens são upsertados pelo `id`, então rodar de novo reconcilia o dataset publicado com o arquivo em vez de duplicar.

Depois, rode o dataset contra o agente:

```bash
make avaliar                                # os 9 itens, nome de run automático
make avaliar ITENS=v0-contagem-categorias   # um item só, poupa cota
make avaliar NOME="prompt v2"               # nomeia o run, para comparar depois
```

Os nove itens somam ~45 chamadas ao LLM, executadas em sequência (`max_concurrency=1`) porque o modelo gratuito tem cota diária e paralelismo garante rate limit. Vale validar com `ITENS=` antes de soltar o dataset inteiro.

O resultado aparece no Langfuse em **Datasets → `agente-sql-regressao-v0` → o run**. Cada item traz o número e um diagnóstico: o `comment` diz o quê (*"Esperado 25. Mencionado na resposta."*) e o `metadata.sequencia_de_tools` diz como (`get_schema → get_descriptions → execute_sql`). Rodar de novo depois de mover o label do prompt dá a comparação item por item.

### Resolução de problemas

| Sintoma | Causa provável |
|---|---|
| Log `usando o prompt embutido no codigo` | Langfuse sem credenciais ou inalcançável; o agente segue com o texto de `src/prompts.py` |
| `[Limite de N iterações atingido...]` | o agente gastou o orçamento da pergunta sem concluir; a pergunta pode ser complexa demais para o modelo escolhido |
| `Falha de infraestrutura no banco alvo` | pool esgotado, conexão morta ou consulta sem resposta; o log do terminal mostra o estado do pool |
| `Rate limit exceeded: free-models-per-day` | cota diária do modelo gratuito do OpenRouter; troque de modelo ou aguarde o reset |
| Traces não aparecem no Langfuse | chaves ausentes no `.env`, ou envio em lote ainda em andamento |
| `Connection refused` na porta 5433/5434 | containers parados; rode `docker compose up -d` dentro de `docker/` |
| `GroundTruthDivergente` ao semear o dataset | o volume do `target_db` foi recriado e um valor estável mudou; o expected pede revisão humana, não sobrescrita |
| `Langfuse sem credenciais configuradas` ao avaliar | o seed do dataset e o runner exigem as chaves, ao contrário da aplicação |
