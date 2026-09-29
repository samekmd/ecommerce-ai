import { interpretar } from '../middlewares/ops/interpretacao.ts'
import { useRequisicao } from './useRequisicao.ts'

// Leva de 5 a 60 s. Reenviar cancela a interpretação anterior; desmontar também.
export function useInterpretar() {
  return useRequisicao(interpretar)
}
