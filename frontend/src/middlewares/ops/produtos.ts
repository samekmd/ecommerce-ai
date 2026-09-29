import { clienteOps } from '../http/clienteOps.ts'
import { cabecalhosCadastro } from './cabecalhos.ts'
import type { OpcoesCadastro, ProdutoCadastro, ProdutoCriado, SkuSugerido } from './tipos.ts'

export async function cadastrarProduto(dados: ProdutoCadastro, opcoes: OpcoesCadastro): Promise<ProdutoCriado> {
  const { data } = await clienteOps.post<ProdutoCriado>('/produtos', dados, {
    headers: cabecalhosCadastro(opcoes),
    signal: opcoes.signal,
  })
  return data
}

// Sugestão, não reserva: outro usuário pode gravar o mesmo SKU antes (409 em sku).
export async function buscarSkuSugerido(categoriaId: number | null, signal?: AbortSignal): Promise<string> {
  const { data } = await clienteOps.get<SkuSugerido>('/produtos/sku-sugerido', {
    params: categoriaId === null ? undefined : { categoria_id: categoriaId },
    signal,
  })
  return data.sku
}
