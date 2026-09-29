# API do query-agent — referência para o frontend

Contrato HTTP do agente Text-to-SQL (`services/query-agent`). Base para o desenvolvimento do frontend.
Gerado a partir do código (`api/main.py` + schemas Pydantic de `api/schemas.py`) em 2026-09-29.

- **Base URL (dev):** `http://localhost:8000` — suba com `make api` em `services/query-agent`.
- **Documentação interativa:** `http://localhost:8000/docs` (Swagger) e
  `http://localhost:8000/openapi.json` (sempre ligados — não há distinção por ambiente).
- **Sem prefixo de versão:** as rotas ficam na raiz (`/perguntas`, `/health`).
- **Formato:** JSON UTF-8 (`Content-Type: application/json`) em todas as requisições e respostas.

---

## 1. Conceito: pergunta em linguagem natural, resposta em conversa

```
1. Usuário digita uma pergunta ──► POST /perguntas { pergunta } ──► { resposta, thread_id }
2. Frontend mostra a `resposta` e guarda o `thread_id` da conversa
3. Pergunta de acompanhamento ──► POST /perguntas { pergunta, thread_id } ──► { resposta, thread_id }
   (o agente lembra das perguntas e respostas anteriores da mesma conversa)
4. "Nova conversa" = enviar sem `thread_id`
```

- **Só leitura.** O agente consulta o banco da loja com um usuário que tem apenas `SELECT`; nenhuma
  pergunta altera dados.
- **Um único banco.** A API atende o e-commerce (`TARGET_DB_LOJA`), resolvido na subida — o cliente
  não escolhe banco.
- **A resposta é texto livre** gerado pelo LLM, em português. Pode conter markdown (listas, tabelas,
  negrito) — recomendado renderizar como markdown.
- Internamente o agente roda um loop ReAct (descobre tabelas → lê colunas → monta e executa SQL →
  corrige erros sozinho). O SQL gerado **não** é devolvido na resposta.

---

## 2. Headers

Nenhum header customizado. Não há `X-Usuario`, autenticação nem `Idempotency-Key`: basta
`Content-Type: application/json` no `POST`.

---

## 3. Formato de erros

Os erros seguem o **formato padrão do FastAPI** (diferente do ops-agent), sempre com a chave `detail`.

**Erros de validação (422)** — lista, um item por problema:
```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "pergunta"],
      "msg": "String should have at least 1 character",
      "input": "",
      "ctx": { "min_length": 1 }
    }
  ]
}
```
- `loc` indica onde está o erro (`["body", "<campo>"]`); o último item é o nome do campo.
- `msg` vem do Pydantic, em inglês.
- Atenção: diferente do ops-agent, **o valor enviado é ecoado** em `input`.

**Demais erros** — mensagem única:
```json
{ "detail": "Erro ao chamar o agente: LLM nao respondeu em 60s." }
```

| Status | Quando | `detail` | O que o frontend deve fazer |
|---|---|---|---|
| `422` | `pergunta` ausente/vazia, tipo errado, JSON inválido | lista (acima) | Não deixar enviar pergunta vazia |
| `500` | Erro de configuração interna do agente | `"Erro de configuracao interna."` | Mensagem genérica |
| `502` | Falha ao chamar o LLM (rede, cota do provedor, timeout de 60 s por chamada) | `"Erro ao chamar o agente: <mensagem da exceção>"` | Tentar de novo em alguns segundos |
| `503` | Banco da loja indisponível (conexão, pool esgotado, query estourou o tempo) | `"Falha de infraestrutura no banco alvo: <mensagem da exceção>"` | Tentar de novo; se persistir, reformular a pergunta |
| `500` | Erro inesperado não tratado | `Internal Server Error` (texto puro) | Mensagem genérica |

- Em `502`/`503` o `detail` inclui o texto da exceção original. Serve para depuração; para o
  usuário final, prefira uma mensagem própria por status.
- **Erro de SQL não é erro HTTP.** Quando a query gerada falha, o agente lê a mensagem do Postgres e
  tenta de novo sozinho; o cliente recebe `200` com a resposta final.

---

## 4. Rotas — visão geral

| Método | Rota | Descrição | Headers |
|---|---|---|---|
| `POST` | `/perguntas` | Pergunta em linguagem natural → resposta do agente | — |
| `GET` | `/health` | Saúde da API e do banco da aplicação | — |

---

## 5. `POST /perguntas`

Responde uma pergunta sobre os dados da loja, iniciando ou continuando uma conversa.

**Latência:** o agente faz várias chamadas encadeadas ao LLM (até **10 iterações**, com teto de
**60 s por chamada**) e executa SQL (teto de **20 s por query**). Espere de alguns segundos a mais de
um minuto. Mostre estado de carregamento, desabilite o reenvio enquanto aguarda e use timeout de
cliente generoso (ex.: **120 s**).

### Requisição
```http
POST /perguntas
Content-Type: application/json

{ "pergunta": "Quantos pedidos foram feitos em 2025?" }
```

| Campo | Tipo | Obrigatório | Regras |
|---|---|---|---|
| `pergunta` | string | sim | mínimo 1 caractere (sem limite máximo) |
| `thread_id` | string \| null | não | Conversa a continuar. Ausente ou `null` → a API abre uma conversa nova. Qualquer string é aceita (não precisa ser UUID) |

Campos extras no corpo são **ignorados** (não geram erro).

### Resposta `200`
```json
{
  "resposta": "Foram feitos **4.812 pedidos** em 2025.",
  "thread_id": "3f6c2a9e-8b1d-4d7a-9f0e-2c5b7a1e4d33"
}
```

| Campo | Tipo | Descrição |
|---|---|---|
| `resposta` | string | Texto final do agente (pode conter markdown) |
| `thread_id` | string | **Sempre devolvido.** Se a requisição não trouxe, é um UUID novo gerado pela API; se trouxe, é o mesmo valor. Reenviar nas próximas perguntas da conversa |

### Pergunta de acompanhamento
```json
{ "pergunta": "E quantos foram cancelados?", "thread_id": "3f6c2a9e-8b1d-4d7a-9f0e-2c5b7a1e4d33" }
```
O agente usa o histórico da conversa para resolver referências ("e quantos...", "desses",
"agora por mês").

### Conversa (`thread_id`) — o que saber
- **A memória fica no processo da API** (em memória, sem persistência). Reiniciar a API (inclusive o
  `--reload` do `make api` ao salvar um arquivo) apaga todas as conversas. Um `thread_id` desconhecido
  **não gera erro**: vira uma conversa nova sem histórico, silenciosamente.
- Não é compartilhada entre réplicas: com mais de uma instância, a mesma conversa precisa cair
  sempre na mesma.
- Guarde o `thread_id` por conversa/aba de chat no frontend (estado ou `sessionStorage`). O botão
  "nova conversa" só descarta o id.
- **Não envie duas perguntas simultâneas no mesmo `thread_id`**: espere a resposta antes da próxima.

### Limites que aparecem na resposta
- **Iterações:** se o agente atingir 10 iterações sem concluir, a resposta termina com o aviso
  `[Limite de 10 iteracoes atingido antes de concluir a consulta; a resposta acima pode estar incompleta.]`.
  Recomendado: detectar o prefixo `[Limite de` e destacar visualmente.
- **Linhas:** cada consulta devolve ao agente no máximo **500 linhas**; resultados maiores são
  truncados e o agente é avisado (a resposta pode dizer isso em texto livre).
- Os valores acima são os padrões (`MAX_ITERACOES`, `MAX_LINHAS_RETORNO`, `OPENROUTER_TIMEOUT_SEGUNDOS`,
  `QUERY_TIMEOUT_SEGUNDOS`) e podem ser alterados no `.env`.

### Erros
`422` (pergunta ausente/vazia) · `502` · `503` · `500`.

---

## 6. Saúde

### `GET /health`
Sempre responde `200`. Checa apenas o **banco da aplicação** (catálogo/metadados do agente) — não
testa o banco da loja nem o LLM.
```json
{ "status": "ok", "app_db": true }
```
```json
{ "status": "degradado", "app_db": false }
```

| Campo | Tipo | Descrição |
|---|---|---|
| `status` | `"ok"` \| `"degradado"` | |
| `app_db` | boolean | Banco da aplicação respondeu a `SELECT 1` |

> Se o catálogo não tiver o banco `TARGET_DB_LOJA` cadastrado, a API **nem sobe** (erro na
> inicialização pedindo para rodar `scripts/seed_catalogo.py`).

---

## 7. Observações de tipos

- `thread_id` é string; quando gerado pela API, é um UUID v4.
- `resposta` é texto; números, datas e valores monetários vêm formatados pelo LLM dentro do texto —
  não há campos estruturados.

### Tipos TypeScript sugeridos

```ts
interface PerguntaRequest {
  pergunta: string;          // min 1 caractere
  thread_id?: string | null; // ausente/null = nova conversa
}

interface PerguntaResponse {
  resposta: string;          // texto (markdown) do agente
  thread_id: string;         // reenviar nas próximas perguntas
}

interface HealthResponse {
  status: "ok" | "degradado";
  app_db: boolean;
}

interface ErroValidacaoItem {
  type: string;
  loc: (string | number)[];  // ex.: ["body", "pergunta"]
  msg: string;
  input?: unknown;
  ctx?: Record<string, unknown>;
}
interface RespostaErroValidacao { detail: ErroValidacaoItem[] } // 422
interface RespostaErroGeral { detail: string }                  // 500, 502, 503
```

---

## 8. Observabilidade

Quando o Langfuse está configurado, cada pergunta gera um trace, e o `thread_id` vira o
`session_id` — todas as perguntas de uma conversa ficam agrupadas numa sessão. Para depurar uma
resposta estranha, basta procurar o `thread_id` no Langfuse. Falha no Langfuse nunca derruba a
pergunta.

---

## 9. CORS

**Não configurado.** Um frontend servido em outra origem (ex.: Vite em `http://localhost:5173`)
terá as requisições bloqueadas pelo navegador. Em dev, use o proxy do dev server:

```ts
// vite.config.ts
export default defineConfig({
  server: {
    proxy: {
      "/perguntas": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
});
```

e chame a API por caminho relativo (`fetch("/perguntas", ...)`). Para servir de outra origem sem
proxy, o backend precisa ganhar um `CORSMiddleware` (pendente).

---

## 10. Exemplo de fluxo completo (curl)

```bash
API=http://localhost:8000

# 1. Saúde
curl -s $API/health

# 2. Nova conversa
curl -s -X POST $API/perguntas -H "Content-Type: application/json" \
  -d '{"pergunta": "Quantos pedidos foram feitos em 2025?"}'

# 3. Acompanhamento (troque o thread_id pelo recebido no passo 2)
curl -s -X POST $API/perguntas -H "Content-Type: application/json" \
  -d '{"pergunta": "E quantos foram cancelados?",
       "thread_id": "3f6c2a9e-8b1d-4d7a-9f0e-2c5b7a1e4d33"}'

# 4. Erro de validação (422)
curl -s -X POST $API/perguntas -H "Content-Type: application/json" -d '{"pergunta": ""}'
```

> As perguntas só leem dados; repetir os exemplos não altera nada no banco. Cada pergunta consome
> cota do provedor de LLM (modelos gratuitos têm limite diário).
