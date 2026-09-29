# CLAUDE.md — ops-agent

Contexto do projeto para agentes de código. Leia antes de alterar qualquer arquivo.

## O que é

Agente de cadastro do e-commerce. Recebe uma frase ("Cadastre 5 camisas da Nike a 100 reais,
fornecedor XYZ") e devolve uma **proposta estruturada** que preenche um formulário no frontend. O
usuário revisa, corrige, anexa a imagem (produto) e confirma. Só então o cadastro é gravado.

Entidades do MVP: **produto, fornecedor, categoria, cupom**. Uma entidade por mensagem.
Monorepo `ecommerce-ai`: este é `services/ops-agent/`; `services/query-agent/` é o text2sql
(somente leitura); código comum em `packages/core/`.

Stack: Python 3.12 · Pydantic AI · Pydantic 2 · FastAPI · OpenRouter · PostgreSQL 16 · SQLAlchemy 2.0

## Princípio central: o agente propõe, o humano confirma, o serviço grava

```
frase ─► POST /interpretar ─► agente (tools de leitura) ─► Proposta ─► formulário (HITL)
                                                                         │ corrige + imagem
banco ◄─ repositories ◄─ services ◄─ POST /produtos (etc.) ◄─ Cadastro ◄─┘
```

1. **O agente nunca escreve no banco nem gera SQL.** Suas tools são tipadas e só leem.
2. **A gravação é um endpoint REST comum**, sem LLM, que revalida tudo. O formulário é entrada não
   confiável: o usuário pode ter editado qualquer campo.

## Estrutura

```
src/ops_agent/
├── config.py            # única fonte de configuração (único módulo que lê ambiente/.env)
├── main.py              # criar_app(): FastAPI, CORS, lifespan, tratadores de erro
├── api/
│   ├── dependencias.py  # headers X-Usuario, X-Interpretacao-Id, Idempotency-Key
│   ├── erros.py         # exceção → status HTTP, formato {"erros": [{campo, mensagem}]}
│   ├── limite_corpo.py  # middleware ASGI: 413 antes de decodificar base64 gigante
│   └── rotas/           # interpretar, produtos, fornecedores, categorias, cupons, saude;
│                        # _cadastro.py: idempotência + service + auditoria
├── agente/
│   ├── agente.py        # instância do Agent: modelo, output_type, tools, instruções
│   ├── deps.py          # dependências injetadas via RunContext
│   ├── prompts/sistema.py
│   └── tools/           # categorias.py, fornecedores.py, cupons.py
├── schemas/             # comum.py, produto.py, fornecedor.py, categoria.py, cupom.py,
│                        # interpretacao.py (união das propostas + PedidoEsclarecimento)
├── services/            # regra de cadastro: validação, unicidade, geração de SKU, transação;
│                        # erros.py (constraint → campo), auditoria.py (app_db)
├── repositories/        # queries; recebem a sessão, nunca a criam
├── models/              # SQLAlchemy das 5 tabelas do banco de negócio, espelhando o DDL;
│                        # auditoria.py: tabelas ops_* do app_db (BaseApp separada)
├── database/            # engine.py (fábrica comum); leitura (tools), escrita (services),
│                        # app (auditoria)
└── observabilidade/     # setup.py (cliente Langfuse, instrument_all), tracing.py (trace por
                         # interpretação)
scripts/seed_prompt.py   # publica a 1ª versão do system prompt no Langfuse
tests/  unit/ · agente/ (FunctionModel, sem rede) · api/ (TestClient) ·
        evals/ (LLM real, fora do CI de PR)
```

Rodar: `make api` (em `services/ops-agent`; `PORTA=` muda a porta padrão 8001), que executa
`uvicorn ops_agent.main:criar_app --factory --reload` (sem `app` global no import).
Testes: `uv run --package ops-agent pytest -q` (precisa do docker compose de pé; sem banco, os
testes de integração são pulados). Nada fica gravado: escrita em savepoint com rollback, auditoria
apagada no teardown.

Dependência: `api → services → repositories → models → database → config` e
`api → agente → tools → repositories`. `schemas/` não importa nenhuma camada. Nunca inverta.

## Schemas: três por entidade, de propósito

| Schema | Quem produz | Diferença |
|---|---|---|
| `XProposta` | o LLM | campos incertos opcionais; tem `avisos`; sem imagem, sem SKU |
| `XCadastro` | o formulário | espelha as constraints do DDL; produto tem imagem e SKU |
| `XCriado`   | o service | inclui o `id` gerado |

Nunca grave a partir da proposta. `Field(description=...)` em todo campo de proposta: é o texto que
o LLM lê. Mudou o DDL (`docker/init-target/01_schema.sql`), mude schemas e models juntos.

## Mapeamento para o banco (o que o DDL impõe)

**produtos** — `categoria_id`, `fornecedor_id`, `nome`, `sku`, `preco`, `estoque` obrigatórios.
- `preco NUMERIC(10,2) > 0` → `Decimal`, `gt=0`, máx. 99.999.999,99. Nunca `float`.
- "5 camisas" → `estoque = 5` de **um** produto, não 5 produtos.
- `sku` é obrigatório e único, e a frase quase nunca o traz. **O agente não gera SKU.** O service
  sugere um (ex.: prefixo da categoria + sequência) para o formulário; o usuário pode editar.
  Conflito no UNIQUE → 409 no campo `sku`.
- Só vincular a fornecedor `ativo = true`.

**categorias** — hierárquica (`categoria_pai_id`). `nome` UNIQUE, mas **sensível a caixa**:
"Camisas" e "camisas" passariam. O service checa duplicidade com `lower(nome)`.
- `listar_categorias` devolve o caminho ("Vestuário > Camisas") e o agente prefere a folha.

**fornecedores** — exige `cnpj`, `cidade`, `estado`, que a frase raramente traz.
- **O agente nunca inventa CNPJ.** Ausente → campo vazio + aviso; o formulário exige.
- O banco não valida CNPJ: normalizar para 14 dígitos e validar dígitos verificadores no schema.
  `estado` validado contra a lista de UFs (o CHECK só olha o tamanho).

**cupons** — **só desconto percentual** (0 < p ≤ 100), `validade_inicio` e `validade_fim`
obrigatórias, `fim >= inicio`. `codigo` UNIQUE sensível a caixa → normalizar para maiúsculas.
- "R$ 20 de desconto" não é suportado → `PedidoEsclarecimento`, nunca converter para percentual.
- Início ausente → hoje. Datas relativas ("até o fim do mês") resolvidas com a data injetada.

**Fora do alcance**: `clientes`, `enderecos`, `pedidos`, `itens_pedido`, `pagamentos`,
`avaliacoes`. Nenhuma tool nem role toca nelas.

## Imagem do produto

Tabela `produtos_imagens` (`docker/init-target/04_produtos_imagens.sql`), 1:1 com `produtos`:
`produto_id` PK/FK `ON DELETE CASCADE`, `conteudo BYTEA`, `mime`, `tamanho_bytes`.
- CHECKs: `ck_produtos_imagens_mime_valido` (jpeg/png/webp), `ck_produtos_imagens_tamanho_positivo`,
  `ck_produtos_imagens_tamanho_coerente` (`tamanho_bytes = octet_length(conteudo)`).
- Base64 é formato de **transporte**: o service decodifica e grava bytes (~25% menor).
- Separada de `produtos` para não cair em `SELECT *` e amostras do text2sql, estourando o contexto
  do LLM. `agente_leitura` não tem SELECT nela (REVOKE explícito, que anula os default privileges
  de `03_permissoes.sql`). Não cadastrar no catálogo do `app_db`.
- Imagem nunca é enviada ao LLM. Validar tamanho máximo (config) e tipo real pelos *magic bytes*
  (JPEG, PNG, WebP), nunca pela extensão ou pelo prefixo `data:`.
- Produto e imagem gravados na **mesma transação**. Com volume, migrar para object storage + URL.

## O agente (Pydantic AI)

- **Saída por união de tipos**: `ProdutoProposta | FornecedorProposta | CategoriaProposta |
  CupomProposta | PedidoEsclarecimento`. O tipo identifica a intenção; sem classificador separado.
- **Validador de saída**: todo ID da proposta precisa ter aparecido num resultado de tool da
  execução. Se não, `ModelRetry` com os válidos. É a defesa contra ID alucinado.
- **Dependências via `RunContext`**: sessão de leitura, usuário, data atual.
- **Stateless** no MVP: uma frase, uma proposta. Correções acontecem no formulário.
- `retries` e limite de requisições por execução sempre definidos. Temperatura baixa.

| Tool (somente leitura) | Devolve |
|---|---|
| `listar_categorias` | `id`, caminho hierárquico |
| `buscar_fornecedores(termo)` | até N ativos por similaridade de nome; nunca a tabela inteira |
| `verificar_codigo_cupom(codigo)` | se o código (normalizado) já existe |

Tools devolvem dado enxuto (sem timestamps); erro de negócio vira texto para o modelo reagir.

**Categoria automática**: o agente escolhe a existente mais adequada e avisa quando a confiança é
baixa. **Nunca cria categoria implicitamente**: se nada encaixa, `categoria_id = None` com sugestão
no aviso. Criar categoria é uma intenção própria.

**System prompt**: papel, entidades, não inventar IDs/CNPJ/SKU, usar tools antes de preencher FKs,
cupom só percentual, português. Não repete os schemas (chegam pelo output_type). Data de hoje
entra por instrução dinâmica, depois do prompt.
- **Versionado no Langfuse**: prompt `ops_agente_sistema`, label `production`. Trocar de versão é
  mover o label na interface, sem redeploy (atraso = `LANGFUSE_PROMPT_CACHE_TTL_SEGUNDOS`).
- `PROMPT_SISTEMA_PADRAO` em `agente/prompts/sistema.py` **não** é a fonte de verdade: é a
  semente (`uv run --package ops-agent python scripts/seed_prompt.py`, que não publica se já
  existir; `--forcar` cria nova versão) e o fallback quando o Langfuse está desligado ou fora.
  Editar o prompt = nova versão no Langfuse, não mudar este arquivo.
- Buscado uma vez por interpretação (`asyncio.to_thread`: o SDK é síncrono), guardado em
  `deps.prompt_sistema`: todas as chamadas ao LLM do run usam a mesma versão. Nunca levanta.

## Observabilidade (Langfuse)

- OpenTelemetry: `Agent.instrument_all()` em `criar_app()` quando há credenciais; o exporter do
  cliente Langfuse recebe os spans do run, de cada chamada ao LLM e de cada tool.
- Cada `/interpretar` abre o span raiz `interpretar` (trace `ops-interpretar`) com `user_id`
  (X-Usuario), tags `ops-agent` e `modelo-<id>`, e `propagate_attributes(prompt=...)`: a
  generation fica ligada à versão do prompt (métricas por versão). Prompt fallback não é ligado.
- `ops_interpretacoes.trace_id` e `prompt_versao` ligam a auditoria ao trace e permitem comparar
  proposta × confirmação por versão de prompt.
- Falha de observabilidade nunca derruba a requisição (`observabilidade/tracing.py` é o único
  lugar com esse `except` amplo); exceção da aplicação atravessa. Erro no trace vai como
  categoria (`retries_esgotados`...), nunca a mensagem da exceção.
- Testes nunca falam com o Langfuse real: `tests/conftest.py` zera `LANGFUSE_PUBLIC_KEY`; os
  testes de tracing usam um cliente com `InMemorySpanExporter`.

## API

| Rota | Faz |
|---|---|
| `POST /api/v1/interpretar` | `{mensagem}` → `{interpretacao_id, tipo, proposta, avisos}` |
| `POST /api/v1/{produtos,fornecedores,categorias,cupons}` | `XCadastro` → grava → 201 `XCriado` |
| `GET /api/v1/categorias`, `/fornecedores?termo=`, `/produtos/sku-sugerido?categoria_id=` | apoio ao formulário |
| `GET /health`, `GET /ready` | liveness (sem banco) e readiness (leitura, escrita e app_db) |

- Headers: `X-Usuario` obrigatório (identifica na auditoria; **não é autenticação**).
  Nos POSTs de cadastro, opcionais: `X-Interpretacao-Id` (o id devolvido pelo `/interpretar`) e
  `Idempotency-Key` (repetição devolve a resposta original sem gravar). Headers, não corpo:
  `XCadastro` tem `extra="forbid"` e continua sendo o contrato puro do formulário.
- Erros de formulário: `{"erros": [{"campo", "mensagem"}]}`. 409 conflito, 422 validação (o valor
  enviado nunca é ecoado), 413 corpo grande. Violação de UNIQUE/CHECK/FK é mapeada pelo nome da
  constraint (`uq_produtos_sku` → `sku`); um teste confere que toda constraint mapeada existe.
- Agente: 502 se não produziu proposta válida (retries/limite), 503 se LLM ou banco caíram.
- Erro inesperado: 500 `{"erro": "Erro interno"}`, nunca a mensagem da exceção.

## Auditoria (`docker/init-app/02_ops_auditoria.sql`)

- `ops_interpretacoes`: usuário, frase, modelo, `tipo` + `proposta` (JSONB) **ou** `erro`
  (categoria, nunca a mensagem), duração.
- `ops_cadastros`: `interpretacao_id`, entidade, payload confirmado (imagem só `{mime,
  tamanho_bytes}`), resultado (`criado|conflito|invalido|erro`), campo do erro, chave de
  idempotência e resposta. Índice único parcial: só cadastro `criado` reserva a chave.
- Falha de auditoria **não derruba a requisição** (não há transação entre bancos): vira log de
  erro. Exceção: a consulta de idempotência, que falha alto para não duplicar cadastro.
- Registrada nas rotas, não no agente: `agente.interpretar()` só devolve a `Interpretacao`.

## Restrições invioláveis

1. **Roles separados.** Tools: `agente_leitura`. Services: `agente_escrita`, com SELECT/INSERT
   em `produtos`, `produtos_imagens`, `fornecedores`, `categorias`, `cupons`, `USAGE` nas sequences
   delas, **sem UPDATE nem DELETE** no MVP. Declarado em `docker/init-target/03_permissoes.sql`
   (grant de `produtos_imagens` em `04_produtos_imagens.sql`, que cria a tabela).
2. **Revalidar tudo na gravação.** Proposta e formulário não são confiáveis.
3. **Transação curta, dentro do service.** Nunca sessão aberta enquanto o LLM responde.
4. **Auditoria no `app_db`**, não no banco de negócio: usuário, frase, proposta, payload confirmado,
   resultado. A diferença proposta × confirmação é a métrica de qualidade do agente.
5. `config.py` é o único leitor de ambiente. Chave do OpenRouter nunca em log nem em trace.

## Armadilhas conhecidas

- Modelos `:free` do OpenRouter falham em tool calling e saída estruturada. Se o agente ignorar
  tools ou gerar JSON inválido, troque o modelo antes de mexer no prompt. Gratuitos (`:free`,
  `openrouter/free`, `stealth/*`) só fora de produção: o `config.py` recusa em `producao`.

## Testes

- `unit/`: schemas (preço, CNPJ, UF, percentual, datas, imagem) e services contra Postgres de teste,
  incluindo cada constraint do DDL virando o erro de campo certo.
- `agente/`: `TestModel`/`FunctionModel`; fluxo de tools, validador, rejeição de ID inventado.
- `evals/`: frase → proposta esperada. Casos obrigatórios: preço por extenso, fornecedor
  inexistente, categoria ambígua, cupom em reais, data relativa, pedido de exclusão (recusar).

## Convenções

- Código e comentários em **português**, sem acentos em identificadores. Comentário explica *por quê*.
- Models espelham o DDL; este serviço não cria nem migra schema.
- Não extrair para `packages/core` sem um segundo consumidor real.

## Fora do escopo do MVP

Edição e exclusão · clientes e pedidos · várias entidades numa frase · conversa com memória.