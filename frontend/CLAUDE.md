# CLAUDE.md — frontend

Contexto do projeto para agentes de código. Leia antes de alterar qualquer arquivo.

## O que é

Interface web do `ecommerce-ai` (pasta `frontend/` do monorepo), com duas abas independentes:

| Aba | API | O que faz |
|---|---|---|
| **Cadastro** | ops-agent (`:8001`) | frase → proposta → formulário revisado pelo usuário (HITL) → gravação |
| **Consultas** | query-agent (`:8000`) | chat em linguagem natural sobre os dados da loja (só leitura) |

Integrar as duas abas numa tela só está fora do escopo do MVP.
Contratos completos: `docs/api-ops-agent.md` e `docs/api-query-agent.md`. **Em dúvida, eles vencem.**

## Stack

React 18 · Vite · TypeScript (strict) · axios · npm

- **Só npm.** `package-lock.json` é versionado; no CI, `npm ci`. Nunca yarn/pnpm.
- **Nenhuma dependência nova sem aprovação.** Estilo com CSS Modules (nativo do Vite). Abas por
  estado, sem roteador. Decisões pendentes: renderizador de markdown (respostas do query-agent) e
  Vitest + Testing Library para testes.

## Estrutura

```
src/
├── assets/          # imagens, ícones, CSS global e variáveis de tema
├── components/
│   ├── comuns/      # Botao, Campo, Alerta, Carregando, SeletorImagem (sem regra de negócio)
│   ├── cadastro/    # CaixaFrase, ListaAvisos, CardEsclarecimento, Form{Produto,Fornecedor,
│   │                # Categoria,Cupom}, AutocompleteFornecedor, SelectCategoria
│   └── consulta/    # Chat, MensagemChat, EntradaPergunta
├── hook/            # useInterpretar, useCadastro, useCategorias, useSkuSugerido,
│                    # useBuscaFornecedores, useConversa, useUsuario (+ provider)
├── middlewares/     # tudo entre a aplicação e as APIs
│   ├── http/        # instâncias axios, interceptors, ErroApi (erro normalizado)
│   ├── ops/         # tipos.ts (contratos) + funções por recurso: interpretacao, produtos, ...
│   └── query/       # tipos.ts + perguntas.ts
├── pages/           # CadastroPage, ConsultaPage (composição, sem chamada HTTP)
├── App.tsx          # abas
└── main.tsx
```

## Direção de dependência

```
pages → components → hook → middlewares → axios
```

- **Só `middlewares/` importa axios.** Componente nunca chama API; hook nunca monta URL nem header.
- `components/` pode importar **tipos** de `middlewares/*/tipos.ts`, nada além disso.
- `components/comuns/` não conhece ops nem query.
- Nunca inverta: `middlewares/` não importa React, hooks nem componentes.

## middlewares/: as duas APIs são diferentes, e a aplicação não deve perceber

| | ops-agent | query-agent |
|---|---|---|
| Prefixo | `/api/v1` | nenhum |
| Headers | `X-Usuario` obrigatório; `X-Interpretacao-Id`, `Idempotency-Key` | nenhum |
| Erro de campo | `{"erros":[{campo, mensagem}]}` (409, 422) | `{"detail":[{loc, msg, input}]}` (422) |
| Erro geral | `{"erro": "..."}` | `{"detail": "..."}` (502/503 trazem texto de exceção) |
| CORS | configurado para `:5173` | **não configurado** |
| Timeout de cliente | 90 s no `/interpretar`, 15 s no resto | 120 s |

Regras:

1. **Proxy do Vite para as duas APIs**, com prefixo próprio, porque ambas têm `/health`:
   `/ops/*` → `:8001` e `/query/*` → `:8000` (com `rewrite` removendo o prefixo). O código chama
   caminhos relativos; em produção o nginx faz o mesmo mapeamento. Bases em `VITE_OPS_API_URL` e
   `VITE_QUERY_API_URL`, com `/ops` e `/query` como padrão.
2. **Uma instância axios por API**, cada uma com seu interceptor de erro.
3. **Todo erro sai como `ErroApi`**: `{ status, geral: string | null, campos: Record<string, string> }`.
   Hook e componente só conhecem esse formato.
   - ops: `campo` vira chave de `campos`; `campo: null` vai para `geral`; `imagem.conteudo_base64`
     é mapeado para `imagem`; prefixo `"Value error, "` é removido.
   - query: o último item de `loc` vira a chave. **O `detail` de 502/503 nunca é exibido**: contém
     texto de exceção interna. Mostrar mensagem própria por status.
   - Mensagens em inglês do Pydantic passam por um mapa de tradução por `type`/texto, com fallback
     genérico em português.
   - Timeout, rede e cancelamento viram `ErroApi` também, com `status: 0`.
4. **`X-Usuario` é injetado por interceptor** da instância ops, lido do `useUsuario`. Formato
   `[A-Za-z0-9._@-]{1,100}`. **Não é autenticação**, só identificação para auditoria.
5. Tipos em `tipos.ts` espelham os documentos das APIs. Mudou a API, mude o tipo no mesmo PR.

## Aba Cadastro (ops-agent)

Fluxo: `CaixaFrase` → `useInterpretar` → formulário do `tipo`, pré-preenchido → confirmar →
`useCadastro` → sucesso ou erros nos campos. Também é possível abrir qualquer formulário vazio,
sem interpretar (cadastro manual).

- **`tipo` é união discriminada.** O `switch` que escolhe o formulário é exaustivo (`never` no
  `default`). `esclarecimento` mostra `proposta.mensagem`, sem formulário.
- **Qualquer campo da proposta pode vir `null`.** O formulário aceita vazio e exige no envio.
- **Avisos** (`avisos`) aparecem em destaque no topo do formulário, nunca escondidos.
- **`/interpretar` leva de 5 a 60 s.** Estado de carregamento visível, botão desabilitado, cancelar
  com `AbortController` ao desmontar ou reenviar.

Headers do cadastro:

- `Idempotency-Key`: `crypto.randomUUID()` **ao abrir o formulário**, não por clique. Mantida em
  reenvios após 409/422; renovada só após sucesso ou nova interpretação.
- `X-Interpretacao-Id`: o `interpretacao_id` recebido. Omitir se veio `null` ou se o cadastro é manual.

Formulário de produto:

- Categoria: `GET /categorias`, exibindo `caminho`; destacar as de `folha: true`.
- SKU: pré-preencher com `GET /produtos/sku-sugerido?categoria_id=`. Buscar de novo ao trocar a
  categoria **só se o usuário não editou o SKU**. É sugestão, não reserva: 409 em `sku` é esperado.
- Fornecedor: autocomplete em `GET /fornecedores?termo=` (mín. 2 caracteres, debounce ~300 ms,
  máx. 5 resultados). Se `fornecedor_id` veio `null`, iniciar a busca com `fornecedor_citado`.
  Lista vazia → oferecer abrir o formulário de fornecedor.
- **Imagem obrigatória.** Validar no cliente **antes** de ler: tipo JPEG/PNG/WebP e tamanho ≤ 2 MB.
  Converter com `FileReader.readAsDataURL` e enviar como `imagem.conteudo_base64` (o prefixo `data:`
  é aceito). Mostrar prévia. O servidor revalida; 413 vira mensagem de tamanho.
- Após `201`, mostrar o registro criado (`id`, SKU final) e limpar o formulário.

Formulário de fornecedor: CNPJ e telefone com máscara na tela, enviados como digitados (o backend
normaliza). UF por select das 27 siglas. Cupom: código em maiúsculas enquanto digita; só percentual.

## Aba Consultas (query-agent)

- `useConversa` guarda mensagens e `thread_id`. Primeira pergunta sem `thread_id`; as seguintes
  reenviam o recebido. "Nova conversa" descarta o id e as mensagens.
- `thread_id` em `sessionStorage` (acesso em `try/catch`), para sobreviver a recarregar a página.
- **Uma pergunta por vez por conversa.** Entrada desabilitada até a resposta chegar.
- A resposta é texto do LLM, possivelmente markdown. **Nunca `dangerouslySetInnerHTML`** com esse
  texto. Enquanto não houver renderizador aprovado, exibir como texto com `white-space: pre-wrap`.
- Resposta terminando com `[Limite de ...]` → destacar como resposta possivelmente incompleta.
- Se a API reiniciar, o `thread_id` passa a abrir uma conversa sem histórico, silenciosamente.
  O frontend não consegue detectar; não tentar.

## Tipos e valores

- **Dinheiro e percentual são `string`** (`type Decimal = string`) no estado, nas propostas e no
  envio. Nunca converter para `number` para enviar. Aceitar vírgula na digitação e normalizar para
  `"100.00"` antes do envio.
- Exibição: `Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })` sobre `Number(valor)`,
  só para mostrar.
- Datas: `YYYY-MM-DD` como string, com `<input type="date">`. Não criar `Date` para datas sem hora
  (o fuso desloca o dia).
- IDs são `number`; `interpretacao_id` e `thread_id` são `string`.
- `strict: true` no `tsconfig`. Sem `any`; use `unknown` e estreite.

## Hooks

- Um hook por caso de uso, devolvendo `{ dados, carregando, erro, executar }` (ou equivalente).
- Hook é o dono do `AbortController` da requisição e cancela no unmount.
- Dados de apoio (categorias) são buscados uma vez por montagem da página; sem cache global no MVP.
- Sem estado global além de `useUsuario`. Nada de Redux/Zustand.

## Segurança

- **Nada secreto em variável `VITE_*`**: ela vai para o bundle público. O frontend não tem chaves.
- Não logar corpo de requisição nem de erro: o 422 do query-agent ecoa o `input` enviado, e o
  formulário carrega CNPJ e imagem.
- Texto vindo do LLM (avisos, mensagem, resposta) é sempre renderizado como texto, nunca como HTML.

## Convenções

- Domínio e identificadores em **português**, sem acentos (`FormProduto`, `useBuscaFornecedores`).
  Nomes de campo iguais aos da API (`categoria_id`, `percentual_desconto`); sem camelCase no contrato.
- Componentes em PascalCase, um por arquivo `.tsx`, com `.module.css` ao lado quando houver estilo.
- Hooks começam com `use`. Funções de `middlewares/` são verbos: `interpretar`, `cadastrarProduto`.
- Comentário explica *por quê*, não *o quê*.
- Acessibilidade: todo campo com `<label>`, erro ligado ao campo por `aria-describedby`,
  carregamento anunciado com `aria-live`.

## Comandos

```bash
npm install          # primeira vez
npm run dev          # Vite em http://localhost:5173 (APIs via proxy)
npm run build        # tsc -b + build de produção; precisa passar antes de qualquer PR
npm run lint
```

Backends, a partir de cada serviço: `make api` (query-agent em `:8000`, ops-agent em `:8001`).

## Antes de concluir uma tarefa

- `npm run build` e `npm run lint` sem erros.
- Testar no navegador o caminho feliz **e** um erro: 409 (SKU repetido), 422 (CNPJ inválido) e
  API desligada (503/rede).
- Conferir que nenhum componente importa axios e que nenhum texto do LLM vira HTML.

## Fora do escopo do MVP

Autenticação real · edição e exclusão · integração das abas · streaming de respostas ·
histórico de conversas persistido · internacionalização.