# CLAUDE.md

Contexto do projeto para agentes de código. Leia antes de alterar qualquer arquivo.

## O que é

Agente Text-to-SQL: recebe uma pergunta em linguagem natural, descobre quais tabelas do banco alvo são relevantes, monta a query e devolve o resultado interpretado.

Construído como agente único em LangGraph, num loop ReAct: o nó do agente decide a próxima ação, o nó de tools executa, e o roteamento decide entre continuar ou finalizar.

## Stack

Python 3.12 · LangGraph · Groq (ChatGroq) · PostgreSQL 16 · SQLAlchemy 2.0 · psycopg3 · Pydantic Settings

## Os dois bancos

A distinção mais importante do projeto. Confundi-los é a origem da maioria dos erros de design aqui.

| | `app_db` | `target_db` |
|---|---|---|
| Papel | metadados do agente | dados de negócio |
| Schema | conhecido, nosso | arbitrário, do cliente |
| Queries | escritas por nós | geradas pelo LLM |
| Acesso | leitura e escrita | somente leitura |
| Confiança | total | nenhuma |
| Abordagem | ORM (`models/`) | `text()` cru com guardrails |
| Porta (dev) | 5433 | 5434 |

**Nunca crie modelos declarativos para tabelas do banco alvo.** O agente precisa consultar qualquer schema, não um que mapeamos. Se surgir essa vontade, algo saiu do lugar.

## Estrutura

```
src/
├── config.py          # única fonte de verdade de configuração
├── graph.py           # grafo LangGraph: nó do agente + ToolNode
├── llm.py             # factory ChatGroq
├── routing.py         # decide entre chamar tool ou finalizar
├── state.py           # estado do agente (histórico de mensagens)
│
├── database/
│   ├── database.py    # engine + sessão do banco da aplicação
│   ├── registry.py    # cache de engines dos bancos alvo
│   └── executor.py    # única porta de entrada de SQL do LLM
│
├── models/            # 5 entidades declarativas do app_db
│   ├── base.py        # Base + TimestampMixin
│   ├── banco.py  tabela.py
│   └── coluna.py  filtro.py  log.py
│
├── repositories/      # queries sobre os modelos
├── services/          # regra de negócio sobre os repositories
└── tools/             # tools expostas ao agente
```

## Direção de dependência

```
tools → services → repositories → models → database → config
```

Nunca inverta. Em particular:

- `database/` contém **apenas** conexão e sessão. Nenhuma query mora ali.
- Repositories **recebem** a sessão como parâmetro, nunca a criam. Quem controla a transação é a tool.
- `config.py` é o único módulo que toca em `os.getenv` ou `.env`.

## As quatro tools

| Tool | Devolve |
|---|---|
| `get_schema` | lista enxuta: nome + descrição de uma linha por tabela |
| `get_descriptions` | detalhe das tabelas pedidas: colunas, tipos, valores de exemplo |
| `get_filters` | filtros de negócio aplicáveis, com instrução de quando usar |
| `execute_sql` | resultado da query, ou a mensagem de erro como texto |

**Recuperação em dois estágios.** `get_schema` é deliberadamente enxuta — só o suficiente para o agente decidir relevância. `get_descriptions` carrega o detalhe pesado apenas das tabelas escolhidas. Se `get_schema` crescer, o padrão perde o sentido e o contexto estoura em bancos grandes.

## Restrições invioláveis

### Segurança

1. **Credenciais nunca no banco.** A tabela `bancos` guarda em `chave_conexao` o *nome* da variável de ambiente (`TARGET_DB_LOJA`), nunca a URL. Resolvido por `config.url_do_banco_alvo()`.

2. **`chave_conexao` é entrada semi-confiável.** Vem do banco, não do código. O formato é validado contra `^TARGET_DB_[A-Z0-9_]+$` **antes** de tocar em `os.getenv` — sem isso, um registro apontando para `GROQ_API_KEY` vazaria o segredo dentro de uma string de conexão.

3. **O usuário read-only é a proteção real.** `agente_leitura` tem só `SELECT`, sem `CREATE` no schema, com `statement_timeout`. A regra "apenas SELECT" no prompt é conveniência — o LLM pode ser induzido a ignorá-la.

4. **Todo SQL do LLM passa por `executor.validar_sql()`.** Nenhuma tool executa `text()` direto no banco alvo.

### Comportamento do agente

5. **Erro de SQL vira texto, nunca exceção.** `executar_consulta` devolve `ResultadoConsulta(sucesso=False, erro=...)`. É assim que o agente lê a mensagem do Postgres e corrige sozinho no próximo passo do loop. Levantar exceção quebra o loop de autocorreção.

6. **Sessão nasce e morre dentro da tool call.** Entre duas tool calls existe uma chamada ao LLM que pode levar segundos. Sessão aberta durante o loop inteiro mantém transação viva e esbarra no `idle_in_transaction_session_timeout`.

7. **Teto de linhas no cliente.** Nunca confie no `LIMIT` que o agente escreveu. `max_linhas_retorno` corta no `executor` e sinaliza `truncado=True`.

8. **O prompt de sistema vive no Langfuse**, não no banco nem no código. `src/prompts.py` busca a versão com o label `production`; trocar de versão é mover esse label na interface do Langfuse — reversível na hora, sem redeploy, com o atraso do cache do SDK (60s).

   O texto em `PROMPT_SISTEMA_PADRAO` **não** é a fonte de verdade: ele é a semente que `scripts/seed_prompt.py` publica num ambiente novo, e o fallback de `get_prompt()` para quando o Langfuse está inalcançável e o cache está vazio. O agente é o caminho crítico e nunca deixa de subir por causa do serviço de observabilidade — ao cair no fallback, loga WARNING.

   Isso reverte a decisão original (prompts na tabela `prompts` do `app_db`, alternados pela flag `ativo`). A tabela, o modelo e o repository foram removidos.

## Armadilhas verificadas

Cada item abaixo causou um bug real neste projeto e foi confirmado em teste.

**`SELECT 1; DROP TABLE x` executa como chamada única.** O SQLAlchemy não bloqueia múltiplos statements e devolve só o último resultado, silenciosamente. `validar_sql` rejeita `;` fora de literal.

**Regex de comando proibido gera falso positivo em string.** `WHERE mensagem LIKE '%DELETE%'` é consulta legítima. Comentários e literais são removidos antes da análise. Ao alterar essa lógica, rode os testes de bypass: `SELECT 'a'; DROP TABLE x` deve continuar bloqueado.

**Pydantic Settings lê o `.env` mas não exporta para `os.environ`.** Como as chaves dos bancos alvo são dinâmicas, `os.getenv("TARGET_DB_*")` voltaria `None`. Por isso o `load_dotenv()` no topo do `config.py`.

**`::int` no Postgres arredonda, não trunca.** `(random() * 4.999)::int` chega a 5. Use `floor()` em qualquer sorteio de índice.

**`CASE` encadeado reavalia `random()` a cada `WHEN`.** As probabilidades se multiplicam em vez de particionar. Materialize o sorteio numa subquery antes do `CASE`.

**`CROSS JOIN LATERAL` sem correlação é avaliado uma vez só.** Uma subquery que não referencia a query externa é materializada e reutilizada em todas as linhas.

**Constraint sem nome explícito diverge do DDL.** `unique=True` inline deixa o Postgres auto-nomear (`bancos_nome_key`), e o Alembic trata como constraint diferente. Sempre use `UniqueConstraint(..., name=...)` em `__table_args__`.

**`atualizado_em` é mantido por trigger no banco.** Use `server_onupdate=FetchedValue()`, nunca `onupdate` do Python — senão viram duas fontes de verdade escrevendo o mesmo campo.

## Otimizações avaliadas e descartadas

**Prompt caching no system prompt.** Não se aplica no estado atual. Medido em setembro de 2026: o prefixo estável reenviado a cada chamada é o system prompt (1.868 chars, ~467 tokens) mais as definições das 4 tools (1.975 chars, ~493 tokens), somando ~960 tokens. Os mínimos de cache por provedor são 1.024 tokens (OpenAI, Claude Sonnet 4.x, Gemini 2.5 Flash), 2.048 (Claude Haiku 3.5) e 4.096 (Claude Opus 4.5–4.8, Haiku 4.5, Gemini 2.5 Pro) — abaixo do mínimo nada é cacheado, e ~960 fica abaixo de todos.

Somam-se dois impedimentos: o modelo em uso é gratuito, sem tier de cache (dos 457 modelos do OpenRouter, 294 têm preço de cache e **nenhum** deles é `:free`), e o TTL padrão de 5 minutos não casa com o ritmo de teste manual.

Para valer a pena seriam necessárias duas coisas ao mesmo tempo: um modelo pago com cache, e cachear o prefixo **inteiro** da conversa — o peso real está nos resultados de `get_schema`/`get_descriptions`, não no system prompt. Antes de tentar, confirmar se o `langchain-openrouter` repassa `cache_control`; isso não foi verificado.

## Convenções

- Código, nomes e comentários em **português**, sem acentos em identificadores.
- Comentário explica *por quê*, não *o quê*. Se o código já diz, não comente.
- Modelos espelham o DDL exatamente. Ao alterar um, altere o outro e rode o teste de drift.
- `echo` do SQLAlchemy nunca ligado para banco alvo: as queries vêm do LLM e poluem o stdout. O registro útil vai para a tabela `logs`.

## Ambiente

```bash
cp .env.example .env
cd docker && docker compose up -d
```

Sobem `app_db` (5433, catálogo vazio) e `target_db` (5434, e-commerce fictício com 10 tabelas e ~13 mil linhas). Os scripts de `init-*/` rodam só na primeira criação do volume; para reaplicar, `docker compose down -v`.

## Teste de drift dos modelos

Depois de qualquer alteração em `models/` ou no DDL, gere o schema a partir das classes num banco separado e compare com o criado pelo DDL. As duas fontes devem produzir colunas, constraints e índices idênticos. Divergência aqui significa que uma migration vai fazer algo inesperado.

## Estado atual

Pronto e testado:

- Ambiente Docker com os dois bancos
- `config.py` com validação e resolução de bancos alvo
- `database/` completo: engine do app, registry com cache thread-safe, executor com guardrails
- `models/` com as 6 entidades, drift zero contra o DDL

A fazer:

- `repositories/` — queries sobre os modelos
- `services/` — regra de negócio, montagem de contexto
- `tools/` — as quatro tools do agente
- `state.py`, `routing.py`, `graph.py`, `llm.py`
- Popular o catálogo descrevendo as 10 tabelas do banco alvo