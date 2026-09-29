import { useEffect } from 'react'
import { buscarFornecedores } from '../middlewares/ops/fornecedores.ts'
import { useRequisicao } from './useRequisicao.ts'

const MINIMO_CARACTERES = 2
const MAXIMO_CARACTERES = 100
const ESPERA_MS = 300

// dados: null = ainda não buscou; [] = nada encontrado (o formulário oferece cadastrar um novo).
export function useBuscaFornecedores(termo: string) {
  const { dados, carregando, erro, executar, limpar } = useRequisicao(buscarFornecedores)

  useEffect(() => {
    const limpo = termo.trim().slice(0, MAXIMO_CARACTERES)
    if (limpo.length < MINIMO_CARACTERES) {
      limpar()
      return
    }
    const espera = setTimeout(() => void executar(limpo), ESPERA_MS)
    return () => clearTimeout(espera)
  }, [termo, executar, limpar])

  return { dados, carregando, erro }
}
