import { useEffect } from 'react'
import { listarCategorias } from '../middlewares/ops/categorias.ts'
import { useRequisicao } from './useRequisicao.ts'

const buscar = (_: void, signal: AbortSignal) => listarCategorias(signal)

// Uma busca por montagem da página, sem cache global. `recarregar` depois de criar categoria.
export function useCategorias() {
  const { dados, carregando, erro, executar } = useRequisicao(buscar)

  useEffect(() => {
    void executar()
  }, [executar])

  return { dados, carregando, erro, recarregar: executar }
}
