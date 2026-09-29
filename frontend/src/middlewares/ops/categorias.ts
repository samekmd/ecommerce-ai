import { clienteOps } from '../http/clienteOps.ts'
import { cabecalhosCadastro } from './cabecalhos.ts'
import type { CategoriaCadastro, CategoriaCriada, CategoriaResumo, OpcoesCadastro } from './tipos.ts'

export async function cadastrarCategoria(dados: CategoriaCadastro, opcoes: OpcoesCadastro): Promise<CategoriaCriada> {
  const { data } = await clienteOps.post<CategoriaCriada>('/categorias', dados, {
    headers: cabecalhosCadastro(opcoes),
    signal: opcoes.signal,
  })
  return data
}

export async function listarCategorias(signal?: AbortSignal): Promise<CategoriaResumo[]> {
  const { data } = await clienteOps.get<CategoriaResumo[]>('/categorias', { signal })
  return data
}
