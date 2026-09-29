# API do ops-agent — referência para o frontend

Contrato HTTP do agente de cadastro (`services/ops-agent`). Base para o desenvolvimento do frontend.
Gerado a partir do código (OpenAPI de `criar_app()` + schemas Pydantic) em 2026-09-29.

- **Base URL (dev):** `http://localhost:8001` — suba com `make api` em `services/ops-agent`.
- **Documentação interativa:** `http://localhost:8001/docs` (Swagger) e
  `http://localhost:8001/openapi.json` (desligados em produção).
- **Prefixo das rotas de negócio:** `/api/v1`. As rotas de saúde ficam na raiz.
- **Formato:** JSON UTF-8 (`Content-Type: application/json`) em todas as requisições e respostas.

---

## 1. Conceito: o agente propõe, o humano confirma

```
1. Usuário digita uma frase ──► POST /api/v1/interpretar ──► { interpretacao_id, tipo, proposta, avisos }
2. Frontend abre o formulário do `tipo`, pré-preenchido com a `proposta`, e mostra os `avisos`
3. Usuário revisa, completa (ex.: CNPJ, SKU, imagem) e confirma
4. Frontend envia o formulário ──► POST /api/v1/{produtos|fornecedores|categorias|cupons}
                                   (headers: X-Usuario, X-Interpretacao-Id, Idempotency-Key)
5. 201 = gravado · 409/422 = erro no campo indicado → mostrar no campo e deixar corrigir
```

- **`/interpretar` nunca grava nada.** Só a rota de cadastro grava, e ela revalida tudo: o
  formulário é tratado como entrada não confiável.
- **Uma entidade por frase.** O `tipo` da resposta decide qual formulário abrir.
- **Não há edição nem exclusão** no MVP (sem PUT/PATCH/DELETE).

---

## 2. Headers

| Header | Onde | Obrigatório | Formato | Para quê |
|---|---|---|---|---|
| `X-Usuario` | `POST /interpretar` e todos os `POST` de cadastro | **sim** | 1–100 caracteres `[A-Za-z0-9._@-]` (sem espaço nem acento) | Identifica quem fez a ação na auditoria e no Langfuse. **Não é autenticação.** Use o login do usuário; envie o mesmo valor na interpretação e no cadastro. |
| `X-Interpretacao-Id` | `POST` de cadastro | não | UUID | O `interpretacao_id` devolvido pelo `/interpretar`. Liga a proposta à confirmação (métrica de qualidade do agente). Omitir se o usuário preencheu o formulário sem interpretar. |
| `Idempotency-Key` | `POST` de cadastro | não (**recomendado**) | 1–200 caracteres | Gere um UUID **por formulário** (não por clique). Reenvio com a mesma chave (duplo clique, retry de rede) devolve a resposta original `201` **sem gravar de novo**. Só cadastros bem-sucedidos reservam a chave: após um 409/422, corrija e reenvie com a mesma chave. |

A chave de idempotência vale **por usuário** (o par `X-Usuario` + `Idempotency-Key`).

---

## 3. Formato de erros

Todas as respostas de erro são JSON. Dois formatos:

**Erros de formulário (409, 422)** — lista de erros por campo:
```json
{ "erros": [ { "campo": "sku", "mensagem": "SKU ja cadastrado" } ] }
```
- `campo` é o nome do campo do corpo (`sku`, `cnpj`, `imagem`, `imagem.conteudo_base64`...), do
  header (`X-Usuario`) ou da query (`termo`).
- `campo` pode ser **`null`** quando o erro envolve mais de um campo (hoje: período do cupom com
  `validade_fim` anterior a `validade_inicio`). Mostre como erro geral do formulário.
- Pode haver **vários erros** na lista (todos os campos inválidos de uma vez).
- O valor enviado **nunca** é devolvido na resposta.
- Mensagens de validação de formato vêm do Pydantic, algumas em inglês e com o prefixo
  `"Value error, "` (ex.: `"Value error, CNPJ invalido"`, `"String should have at least 1 character"`).
  Recomendado: remover o prefixo e, se quiser, traduzir por `campo` no frontend. Mensagens de
  regra de negócio (conflitos, FK) já vêm em português (seção 8).

**Demais erros** — mensagem única, sempre genérica:
```json
{ "erro": "Erro interno" }
```

| Status | Quando | Corpo | O que o frontend deve fazer |
|---|---|---|---|
| `409` | Duplicidade (SKU, CNPJ, nome de categoria, código de cupom) | `{"erros": [...]}` | Marcar o campo; usuário altera o valor |
| `413` | Corpo acima do limite (imagem grande demais antes mesmo de validar) | `{"erro": "Requisicao maior que o limite permitido"}` | Avisar tamanho máximo da imagem (seção 6.1) |
| `422` | Validação de formato ou regra que depende do banco (FK inexistente, fornecedor inativo, imagem inválida) | `{"erros": [...]}` | Marcar os campos |
| `500` | Erro inesperado | `{"erro": "Erro interno"}` | Mensagem genérica; tentar de novo |
| `502` | O agente não produziu uma proposta válida (só `/interpretar`) | `{"erro": "O agente nao conseguiu interpretar a frase. Tente reformular."}` | Pedir para reformular a frase ou abrir o formulário vazio |
| `503` | LLM indisponível/sobrecarregado ou banco fora do ar | `{"erro": "Servico de interpretacao indisponivel. Tente novamente."}` ou `{"erro": "Banco de dados indisponivel. Tente novamente."}` | Tentar de novo em alguns segundos |

---

## 4. Rotas — visão geral

| Método | Rota | Descrição | Headers |
|---|---|---|---|
| `POST` | `/api/v1/interpretar` | Frase → proposta de cadastro | `X-Usuario` |
| `POST` | `/api/v1/produtos` | Grava produto (com imagem) | `X-Usuario`, `X-Interpretacao-Id`?, `Idempotency-Key`? |
| `GET` | `/api/v1/produtos/sku-sugerido?categoria_id=` | Sugere um SKU livre | — |
| `POST` | `/api/v1/fornecedores` | Grava fornecedor | `X-Usuario`, `X-Interpretacao-Id`?, `Idempotency-Key`? |
| `GET` | `/api/v1/fornecedores?termo=` | Busca fornecedores ativos por nome | — |
| `POST` | `/api/v1/categorias` | Grava categoria | `X-Usuario`, `X-Interpretacao-Id`?, `Idempotency-Key`? |
| `GET` | `/api/v1/categorias` | Lista categorias com caminho hierárquico | — |
| `POST` | `/api/v1/cupons` | Grava cupom | `X-Usuario`, `X-Interpretacao-Id`?, `Idempotency-Key`? |
| `GET` | `/health` | Liveness (não toca no banco) | — |
| `GET` | `/ready` | Readiness (checa os bancos) | — |

---

## 5. `POST /api/v1/interpretar`

Transforma uma frase em linguagem natural numa proposta de cadastro.

**Latência:** usa um LLM com várias chamadas encadeadas — espere **de 5 a 60 segundos**. Mostre
estado de carregamento, desabilite o reenvio enquanto aguarda e use timeout de cliente de pelo
menos **90 s**.

### Requisição
```http
POST /api/v1/interpretar
Content-Type: application/json
X-Usuario: samuel

{ "mensagem": "Cadastre 5 camisas da Nike a 100 reais, fornecedor Casa 1" }
```

| Campo | Tipo | Regras |
|---|---|---|
| `mensagem` | string | obrigatório, 1–1000 caracteres |

### Resposta `200`
```json
{
  "interpretacao_id": "bcc367bf-e8bb-4e94-9474-5782a1078240",
  "tipo": "produto",
  "proposta": {
    "avisos": ["CNPJ do fornecedor ausente."],
    "nome": "Camisas da Nike",
    "preco": "100",
    "estoque": 5,
    "categoria_id": 14,
    "fornecedor_id": 1,
    "fornecedor_citado": "Casa 1"
  },
  "avisos": ["CNPJ do fornecedor ausente."]
}
```

| Campo | Tipo | Descrição |
|---|---|---|
| `interpretacao_id` | string (UUID) \| `null` | Reenviar em `X-Interpretacao-Id` no cadastro. `null` se a auditoria falhou — o fluxo segue normalmente, só não envie o header. |
| `tipo` | `"produto"` \| `"fornecedor"` \| `"categoria"` \| `"cupom"` \| `"esclarecimento"` | Qual formulário abrir (ou, em `esclarecimento`, mostrar a mensagem). |
| `proposta` | objeto | Formato depende do `tipo` (abaixo). |
| `avisos` | string[] | Pontos que o usuário precisa conferir ou completar. Mesmo conteúdo de `proposta.avisos` (vazio em `esclarecimento`). Mostre em destaque no formulário. |

**Todos os campos da proposta podem vir `null`** (exceto os indicados): o agente só preenche o que a
frase trouxe. O formulário deve deixar o usuário completar.

### `proposta` quando `tipo = "produto"`
| Campo | Tipo | Observação |
|---|---|---|
| `nome` | string | sempre presente |
| `preco` | **string decimal** \| null | ex.: `"100"`, `"99.9"` — ver seção 9 |
| `estoque` | integer \| null | "5 camisas" → `5` (um produto com estoque 5) |
| `categoria_id` | integer \| null | id existente, validado contra `GET /categorias`. `null` → usuário escolhe |
| `fornecedor_id` | integer \| null | id de fornecedor ativo. `null` → usar `fornecedor_citado` para buscar em `GET /fornecedores?termo=` |
| `fornecedor_citado` | string \| null | nome do fornecedor como veio na frase |
| `avisos` | string[] | |

A proposta **não traz SKU nem imagem**: o SKU vem de `GET /produtos/sku-sugerido` e a imagem é
anexada pelo usuário.

### `proposta` quando `tipo = "fornecedor"`
| Campo | Tipo | Observação |
|---|---|---|
| `nome` | string | sempre presente |
| `cnpj` | string \| null | só se estava na frase (o agente nunca inventa); pode vir com máscara e **sem validação** — o cadastro valida |
| `email_contato` | string \| null | |
| `telefone` | string \| null | |
| `cidade` | string \| null | |
| `estado` | string \| null | sigla da UF |
| `avisos` | string[] | |

### `proposta` quando `tipo = "categoria"`
| Campo | Tipo | Observação |
|---|---|---|
| `nome` | string | sempre presente |
| `categoria_pai_id` | integer \| null | `null` = categoria raiz |
| `avisos` | string[] | |

### `proposta` quando `tipo = "cupom"`
| Campo | Tipo | Observação |
|---|---|---|
| `codigo` | string \| null | já normalizado em maiúsculas |
| `percentual_desconto` | **string decimal** \| null | 0 < p ≤ 100. Só percentual existe |
| `validade_inicio` | string `YYYY-MM-DD` | se a frase não disser, vem **hoje** |
| `validade_fim` | string `YYYY-MM-DD` \| null | datas relativas ("até o fim do mês") já resolvidas |
| `avisos` | string[] | |

### `proposta` quando `tipo = "esclarecimento"`
O agente não conseguiu (ou não pode) propor um cadastro. Mostre a `mensagem` ao usuário; não há
formulário.

| Campo | Tipo | Observação |
|---|---|---|
| `motivo` | `"ambiguo"` \| `"nao_suportado"` \| `"fora_do_escopo"` | `ambiguo`: falta informação · `nao_suportado`: pedido entendido mas não permitido (desconto em reais, editar, excluir, várias entidades) · `fora_do_escopo`: não é cadastro de produto/fornecedor/categoria/cupom |
| `mensagem` | string | Pergunta ou explicação em português, pronta para exibir |

```json
{
  "interpretacao_id": "…",
  "tipo": "esclarecimento",
  "proposta": {
    "motivo": "nao_suportado",
    "mensagem": "Desconto em reais (R$ 20) não é suportado. Qual percentual de desconto deseja?"
  },
  "avisos": []
}
```

### Erros
`422` (mensagem vazia/longa, `X-Usuario` ausente/inválido) · `502` · `503` · `500`.

---

## 6. Rotas de cadastro

Todas: `201 Created` com o registro criado; `409`/`422` com `{"erros": [...]}`.
O corpo aceita **somente os campos listados** — qualquer campo extra gera `422`
(`"Extra inputs are not permitted"`). Espaços no início/fim de strings são removidos.

### 6.1 `POST /api/v1/produtos`

```http
POST /api/v1/produtos
Content-Type: application/json
X-Usuario: samuel
X-Interpretacao-Id: bcc367bf-e8bb-4e94-9474-5782a1078240
Idempotency-Key: 5f0b7c1e-3a1b-4c1e-9a52-0d6c2b1f8e11

{
  "nome": "Camisa Nike Dri-FIT",
  "sku": "ROU-000001",
  "preco": "100.00",
  "estoque": 5,
  "categoria_id": 14,
  "fornecedor_id": 1,
  "imagem": { "conteudo_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC" }
}
```

| Campo | Tipo | Obrigatório | Regras |
|---|---|---|---|
| `nome` | string | sim | não vazio |
| `sku` | string | sim | não vazio; único (use `GET /produtos/sku-sugerido`; o usuário pode editar) |
| `preco` | string decimal ou number | sim | > 0, até 2 casas, máx. `99999999.99`. **Prefira enviar string** (`"100.00"`) |
| `estoque` | integer | sim | ≥ 0 |
| `categoria_id` | integer | sim | > 0; precisa existir |
| `fornecedor_id` | integer | sim | > 0; precisa existir **e estar ativo** |
| `imagem` | objeto | **sim** | `{ "conteudo_base64": string }` |
| `imagem.conteudo_base64` | string | sim | base64 de uma imagem **JPEG, PNG ou WebP**; aceita (e ignora) o prefixo `data:image/...;base64,` |

**Imagem:**
- O tipo é detectado pelo **conteúdo** do arquivo, não pela extensão nem pelo prefixo `data:`.
  GIF, SVG, PDF etc. → `422` no campo `imagem`.
- **Tamanho máximo: 2 MB** (2.097.152 bytes da imagem decodificada; configurável no backend via
  `OPS_IMAGEM_MAX_BYTES`). Acima disso → `422` `"Imagem maior que o limite de 2048 KB"`; muito
  acima → `413`. Valide o tamanho no frontend antes de enviar.
- Base64 é só transporte: a imagem **não volta** em nenhuma resposta e nunca é enviada ao LLM.
- Para gerar no navegador: `FileReader.readAsDataURL(file)` e enviar o resultado direto (o prefixo
  `data:` é aceito).

**Resposta `201`:**
```json
{
  "id": 501,
  "nome": "Camisa Nike Dri-FIT",
  "sku": "ROU-000001",
  "preco": "100.00",
  "estoque": 5,
  "categoria_id": 14,
  "fornecedor_id": 1
}
```

**Erros de negócio:** `409 sku` (SKU já cadastrado) · `422 categoria_id` (Categoria inexistente) ·
`422 fornecedor_id` (Fornecedor inexistente ou inativo) · `422 imagem` (tipo ou tamanho).

### 6.2 `GET /api/v1/produtos/sku-sugerido`

Sugere o próximo SKU livre para o formulário de produto. É **sugestão, não reserva**: dois
usuários podem receber o mesmo valor; quem gravar depois recebe `409` no `sku`.

| Query | Tipo | Obrigatório | Regras |
|---|---|---|---|
| `categoria_id` | integer | não | > 0. Define o prefixo: 3 primeiras letras da categoria sem acento (`"Roupas Masculinas"` → `ROU`). Sem categoria (ou categoria inexistente/nome curto) → prefixo `SKU` |

```http
GET /api/v1/produtos/sku-sugerido?categoria_id=14
```
```json
{ "sku": "ROU-000001" }
```
Formato: `PREFIXO-NNNNNN` (6 dígitos). Recomendado: buscar de novo quando o usuário trocar a
categoria.

### 6.3 `POST /api/v1/fornecedores`

```json
{
  "nome": "XYZ Comercio Ltda",
  "cnpj": "11.222.333/0001-81",
  "email_contato": "contato@xyz.com.br",
  "telefone": "(19) 98765-4321",
  "cidade": "Campinas",
  "estado": "sp"
}
```

| Campo | Tipo | Obrigatório | Regras / normalização |
|---|---|---|---|
| `nome` | string | sim | não vazio |
| `cnpj` | string | sim | aceita com ou sem máscara; **dígitos verificadores validados**; gravado com 14 dígitos; único |
| `email_contato` | string \| null | não | e-mail válido |
| `telefone` | string \| null | não | aceita máscara; DDD + número = 10 ou 11 dígitos; gravado só com dígitos |
| `cidade` | string | sim | não vazio |
| `estado` | string | sim | sigla de UF válida (27 UFs); aceita minúsculas, gravada em maiúsculas |

**Resposta `201`:**
```json
{
  "id": 61,
  "nome": "XYZ Comercio Ltda",
  "cnpj": "11222333000181",
  "email_contato": "contato@xyz.com.br",
  "telefone": "19987654321",
  "cidade": "Campinas",
  "estado": "SP",
  "ativo": true
}
```

**Erros:** `409 cnpj` (CNPJ já cadastrado) · `422 cnpj` (`CNPJ invalido`) · `422 estado`
(`UF invalida`) · `422 telefone` · `422 email_contato`.

### 6.4 `GET /api/v1/fornecedores?termo=`

Busca fornecedores **ativos** cujo nome contém o termo (sem diferenciar maiúsculas). Quem começa
com o termo vem primeiro. Devolve **no máximo 5** (configurável: `OPS_MAX_FORNECEDORES_BUSCA`) —
use como autocomplete, não como listagem completa.

| Query | Tipo | Obrigatório | Regras |
|---|---|---|---|
| `termo` | string | sim | 2–100 caracteres. `%` e `_` são tratados como texto literal |

```http
GET /api/v1/fornecedores?termo=casa
```
```json
[
  { "id": 1, "nome": "Casa 1", "cidade": "Recife", "estado": "SP" }
]
```
Lista vazia = nenhum fornecedor ativo com esse nome (o usuário pode cadastrar um novo).

### 6.5 `POST /api/v1/categorias`

```json
{ "nome": "Camisetas", "categoria_pai_id": 14 }
```

| Campo | Tipo | Obrigatório | Regras |
|---|---|---|---|
| `nome` | string | sim | não vazio; único **sem diferenciar maiúsculas** (`"moda"` conflita com `"Moda"`) |
| `categoria_pai_id` | integer \| null | não | > 0 e existente; `null`/omitido = categoria raiz |

**Resposta `201`:**
```json
{ "id": 26, "nome": "Camisetas", "categoria_pai_id": 14 }
```

**Erros:** `409 nome` (Categoria ja cadastrada) · `422 categoria_pai_id` (Categoria pai inexistente).

### 6.6 `GET /api/v1/categorias`

Lista **todas** as categorias com o caminho hierárquico, ordenadas pelo caminho. Use para o
select de categoria (prefira categorias com `folha: true` para produtos).

```json
[
  { "id": 1,  "caminho": "Eletronicos", "folha": true },
  { "id": 7,  "caminho": "Brinquedos", "folha": false },
  { "id": 14, "caminho": "Brinquedos > Roupas Masculinas", "folha": true }
]
```

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | integer | |
| `caminho` | string | `"Pai > Filha"` |
| `folha` | boolean | `true` se não tem subcategorias |

### 6.7 `POST /api/v1/cupons`

```json
{
  "codigo": "black15",
  "percentual_desconto": "15",
  "validade_inicio": "2026-10-01",
  "validade_fim": "2026-10-31"
}
```

| Campo | Tipo | Obrigatório | Regras / normalização |
|---|---|---|---|
| `codigo` | string | sim | 3–30 caracteres entre `A-Z`, `0-9`, `_` e `-` (sem espaços); aceita minúsculas e grava em **maiúsculas**; único sem diferenciar maiúsculas |
| `percentual_desconto` | string decimal ou number | sim | > 0 e ≤ 100, até 2 casas. **Só desconto percentual existe** |
| `validade_inicio` | string `YYYY-MM-DD` | sim | |
| `validade_fim` | string `YYYY-MM-DD` | sim | ≥ `validade_inicio` (senão `422` com **`campo: null`**) |

**Resposta `201`:**
```json
{
  "id": 61,
  "codigo": "BLACK15",
  "percentual_desconto": "15.00",
  "validade_inicio": "2026-10-01",
  "validade_fim": "2026-10-31",
  "ativo": true
}
```

**Erros:** `409 codigo` (Codigo de cupom ja cadastrado) · `422 codigo` (formato) ·
`422 percentual_desconto` · `422` com `campo: null` (período inválido).

---

## 7. Saúde

### `GET /health`
Liveness: o processo responde. Não toca no banco.
```json
{ "status": "ok" }
```

### `GET /ready`
Readiness: os três bancos respondem. `200` quando todos estão ok, `503` quando algum falha
(mesmo corpo).
```json
{ "status": "ok", "bancos": { "leitura": true, "escrita": true, "app": true } }
```
```json
{ "status": "indisponivel", "bancos": { "leitura": true, "escrita": false, "app": true } }
```

---

## 8. Mensagens de erro de negócio (texto exato)

| Status | `campo` | `mensagem` |
|---|---|---|
| 409 | `sku` | `SKU ja cadastrado` |
| 409 | `cnpj` | `CNPJ ja cadastrado` |
| 409 | `nome` | `Categoria ja cadastrada` |
| 409 | `codigo` | `Codigo de cupom ja cadastrado` |
| 422 | `categoria_id` | `Categoria inexistente` |
| 422 | `fornecedor_id` | `Fornecedor inexistente ou inativo` |
| 422 | `categoria_pai_id` | `Categoria pai inexistente` |
| 422 | `imagem` | `Imagem maior que o limite de 2048 KB` |
| 422 | `imagem` | `Value error, imagem deve ser JPEG, PNG ou WebP` |
| 422 | `imagem` | `Value error, imagem nao e base64 valido` |
| 422 | `cnpj` | `Value error, CNPJ invalido` |
| 422 | `estado` | `Value error, UF invalida` |
| 422 | `telefone` | `Value error, telefone deve ter DDD + numero (10 ou 11 digitos)` |
| 422 | `null` | `Value error, validade_fim deve ser igual ou posterior a validade_inicio` |
| 422 | `X-Usuario` | `Field required` (header ausente) |

Os demais `422` de formato (campo vazio, número fora da faixa, tipo errado) usam as mensagens
padrão do Pydantic, em inglês.

---

## 9. Observações de tipos

- **Valores monetários e percentuais vêm como string decimal** nas respostas
  (`"preco": "100.00"`, `"percentual_desconto": "15.00"`, e na proposta `"preco": "100"`), para
  não perder precisão. O OpenAPI descreve os campos da proposta como `number`, mas o JSON real é
  string. Converta com cuidado (ex.: exibir com `Intl.NumberFormat` após `Number(valor)`, ou usar
  uma lib decimal) e, ao enviar, prefira string com 2 casas.
- **Datas** são `YYYY-MM-DD` sem hora. "Hoje" é calculado no fuso `America/Sao_Paulo`.
- **IDs** são inteiros; `interpretacao_id` é UUID string.

### Tipos TypeScript sugeridos

```ts
type Decimal = string; // "100.00"

type TipoInterpretacao = "produto" | "fornecedor" | "categoria" | "cupom" | "esclarecimento";

interface ProdutoProposta {
  nome: string;
  preco: Decimal | null;
  estoque: number | null;
  categoria_id: number | null;
  fornecedor_id: number | null;
  fornecedor_citado: string | null;
  avisos: string[];
}
interface FornecedorProposta {
  nome: string;
  cnpj: string | null;
  email_contato: string | null;
  telefone: string | null;
  cidade: string | null;
  estado: string | null;
  avisos: string[];
}
interface CategoriaProposta { nome: string; categoria_pai_id: number | null; avisos: string[] }
interface CupomProposta {
  codigo: string | null;
  percentual_desconto: Decimal | null;
  validade_inicio: string | null; // YYYY-MM-DD
  validade_fim: string | null;
  avisos: string[];
}
interface PedidoEsclarecimento {
  motivo: "ambiguo" | "nao_suportado" | "fora_do_escopo";
  mensagem: string;
}

type RespostaInterpretar =
  | { interpretacao_id: string | null; tipo: "produto"; proposta: ProdutoProposta; avisos: string[] }
  | { interpretacao_id: string | null; tipo: "fornecedor"; proposta: FornecedorProposta; avisos: string[] }
  | { interpretacao_id: string | null; tipo: "categoria"; proposta: CategoriaProposta; avisos: string[] }
  | { interpretacao_id: string | null; tipo: "cupom"; proposta: CupomProposta; avisos: string[] }
  | { interpretacao_id: string | null; tipo: "esclarecimento"; proposta: PedidoEsclarecimento; avisos: string[] };

interface ProdutoCadastro {
  nome: string;
  sku: string;
  preco: Decimal;
  estoque: number;
  categoria_id: number;
  fornecedor_id: number;
  imagem: { conteudo_base64: string };
}
interface ProdutoCriado {
  id: number; nome: string; sku: string; preco: Decimal;
  estoque: number; categoria_id: number; fornecedor_id: number;
}

interface FornecedorCadastro {
  nome: string; cnpj: string; email_contato?: string | null; telefone?: string | null;
  cidade: string; estado: string;
}
interface FornecedorCriado extends Required<FornecedorCadastro> { id: number; ativo: boolean }
interface FornecedorResumo { id: number; nome: string; cidade: string; estado: string }

interface CategoriaCadastro { nome: string; categoria_pai_id?: number | null }
interface CategoriaCriada { id: number; nome: string; categoria_pai_id: number | null }
interface CategoriaResumo { id: number; caminho: string; folha: boolean }

interface CupomCadastro {
  codigo: string; percentual_desconto: Decimal; validade_inicio: string; validade_fim: string;
}
interface CupomCriado extends CupomCadastro { id: number; ativo: boolean }

interface SkuSugerido { sku: string }

interface ErroCampo { campo: string | null; mensagem: string }
interface RespostaErrosFormulario { erros: ErroCampo[] }   // 409, 422
interface RespostaErroGeral { erro: string }               // 413, 500, 502, 503
```

---

## 10. Mapeamento proposta → formulário

| `tipo` | Pré-preencher com a proposta | O usuário completa | Chamadas de apoio |
|---|---|---|---|
| `produto` | `nome`, `preco`, `estoque`, `categoria_id`, `fornecedor_id` | `sku` (pré-preencher com a sugestão), **imagem**, campos `null` | `GET /categorias` (select), `GET /produtos/sku-sugerido?categoria_id=`, `GET /fornecedores?termo={fornecedor_citado}` se `fornecedor_id` for `null` |
| `fornecedor` | todos os campos | `cnpj`, `cidade`, `estado` (a frase raramente traz) | — |
| `categoria` | `nome`, `categoria_pai_id` | — | `GET /categorias` (select do pai) |
| `cupom` | todos os campos | `validade_fim` se `null` | — |
| `esclarecimento` | — (sem formulário) | — | Mostrar `proposta.mensagem`; o usuário reformula a frase |

O usuário também pode abrir qualquer formulário **sem** passar pelo `/interpretar` (preenchimento
manual) — nesse caso, apenas não envie `X-Interpretacao-Id`.

---

## 11. CORS

- Origens permitidas (dev): `http://localhost:5173` (configurável em `OPS_CORS_ORIGENS`, lista
  separada por vírgula).
- Métodos: `GET`, `POST`.
- Headers permitidos: `Content-Type`, `X-Usuario`, `X-Interpretacao-Id`, `Idempotency-Key`.

---

## 12. Exemplo de fluxo completo (curl)

```bash
API=http://localhost:8001/api/v1

# 1. Interpretar
curl -s -X POST $API/interpretar -H "Content-Type: application/json" -H "X-Usuario: samuel" \
  -d '{"mensagem": "Cadastre 5 camisas da Nike a 100 reais, fornecedor Casa 1"}'

# 2. Apoio ao formulário
curl -s $API/categorias
curl -s "$API/produtos/sku-sugerido?categoria_id=14"
curl -s "$API/fornecedores?termo=casa"

# 3. Confirmar (troque X-Interpretacao-Id pelo id recebido no passo 1)
curl -s -X POST $API/produtos -H "Content-Type: application/json" \
  -H "X-Usuario: samuel" \
  -H "X-Interpretacao-Id: bcc367bf-e8bb-4e94-9474-5782a1078240" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{"nome":"Camisa Nike","sku":"ROU-000001","preco":"100.00","estoque":5,
       "categoria_id":14,"fornecedor_id":1,
       "imagem":{"conteudo_base64":"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC"}}'
```

> Os cadastros gravam de verdade no banco `loja` (não há exclusão pela API). Repetir o mesmo
> exemplo resulta em `409` — troque `sku`, `cnpj`, `nome` ou `codigo` para um novo sucesso.
