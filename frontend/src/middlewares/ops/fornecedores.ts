import { clienteOps } from '../http/clienteOps.ts'
import { cabecalhosCadastro } from './cabecalhos.ts'
import type { FornecedorCadastro, FornecedorCriado, FornecedorResumo, OpcoesCadastro } from './tipos.ts'

export async function cadastrarFornecedor(dados: FornecedorCadastro, opcoes: OpcoesCadastro): Promise<FornecedorCriado> {
  const { data } = await clienteOps.post<FornecedorCriado>('/fornecedores', dados, {
    headers: cabecalhosCadastro(opcoes),
    signal: opcoes.signal,
  })
  return data
}

// Só ativos e no máximo 5: serve para autocomplete, não para listagem.
export async function buscarFornecedores(termo: string, signal?: AbortSignal): Promise<FornecedorResumo[]> {
  const { data } = await clienteOps.get<FornecedorResumo[]>('/fornecedores', { params: { termo }, signal })
  return data
}
