import { clienteOps } from '../http/clienteOps.ts'
import { cabecalhosCadastro } from './cabecalhos.ts'
import type { CupomCadastro, CupomCriado, OpcoesCadastro } from './tipos.ts'

export async function cadastrarCupom(dados: CupomCadastro, opcoes: OpcoesCadastro): Promise<CupomCriado> {
  const { data } = await clienteOps.post<CupomCriado>('/cupons', dados, {
    headers: cabecalhosCadastro(opcoes),
    signal: opcoes.signal,
  })
  return data
}
