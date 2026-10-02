// Contratos do query-agent, espelhando docs/api-query-agent.md. Mudou a API, muda aqui no mesmo PR.

export interface PerguntaRequest {
  pergunta: string
  // Ausente = nova conversa.
  thread_id?: string | null
}

export interface PerguntaResponse {
  // Texto do LLM, possivelmente markdown: exibir sempre como texto, nunca como HTML.
  resposta: string
  // Sempre devolvido; reenviar nas próximas perguntas da conversa.
  thread_id: string
}

// Reexportado para que componentes exibam erros sem importar a camada http.
export type { ErroApi } from '../http/ErroApi.ts'
