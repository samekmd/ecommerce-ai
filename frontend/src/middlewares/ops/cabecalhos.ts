import type { OpcoesCadastro } from './tipos.ts'

// X-Usuario não entra aqui: o interceptor do clienteOps injeta em toda requisição.
export function cabecalhosCadastro({ idempotencyKey, interpretacaoId }: OpcoesCadastro): Record<string, string> {
  const cabecalhos: Record<string, string> = { 'Idempotency-Key': idempotencyKey }
  // Cadastro manual ou auditoria que falhou: o header é omitido, nunca enviado vazio.
  if (interpretacaoId !== null) cabecalhos['X-Interpretacao-Id'] = interpretacaoId
  return cabecalhos
}
