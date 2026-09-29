import { TIMEOUT_INTERPRETAR, clienteOps } from '../http/clienteOps.ts'
import type { RespostaInterpretar } from './tipos.ts'

// Nunca grava nada: só a rota de cadastro grava, depois da revisão do usuário.
export async function interpretar(mensagem: string, signal?: AbortSignal): Promise<RespostaInterpretar> {
  const { data } = await clienteOps.post<RespostaInterpretar>(
    '/interpretar',
    { mensagem },
    { timeout: TIMEOUT_INTERPRETAR, signal },
  )
  return data
}
