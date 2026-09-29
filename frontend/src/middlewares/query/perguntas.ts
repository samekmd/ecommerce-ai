import { clienteQuery } from '../http/clienteQuery.ts'
import type { PerguntaRequest, PerguntaResponse } from './tipos.ts'

// Não enviar outra pergunta no mesmo thread_id antes desta responder: quem garante é o hook.
export async function perguntar(
  pergunta: string,
  threadId: string | null,
  signal?: AbortSignal,
): Promise<PerguntaResponse> {
  const corpo: PerguntaRequest = threadId === null ? { pergunta } : { pergunta, thread_id: threadId }
  const { data } = await clienteQuery.post<PerguntaResponse>('/perguntas', corpo, { signal })
  return data
}
