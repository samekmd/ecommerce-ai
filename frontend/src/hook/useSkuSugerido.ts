import { useCallback, useEffect, useState } from 'react'
import { buscarSkuSugerido } from '../middlewares/ops/produtos.ts'
import { useRequisicao } from './useRequisicao.ts'

// O hook é dono do valor do SKU para garantir a regra: trocar a categoria só busca uma nova
// sugestão enquanto o usuário não tiver editado o campo. A sugestão não reserva o SKU.
export function useSkuSugerido(categoriaId: number | null) {
  const { dados, carregando, erro, executar, cancelar } = useRequisicao(buscarSkuSugerido)
  // null = o usuário não mexeu; qualquer string (inclusive vazia) = valor digitado por ele.
  const [skuDigitado, setSkuDigitado] = useState<string | null>(null)
  const [rodada, setRodada] = useState(0)
  const editado = skuDigitado !== null

  useEffect(() => {
    if (!editado) void executar(categoriaId)
  }, [categoriaId, editado, rodada, executar])

  const alterarSku = useCallback(
    (valor: string) => {
      // Uma sugestão que chegasse agora sobrescreveria o que o usuário acabou de digitar.
      cancelar()
      setSkuDigitado(valor)
    },
    [cancelar],
  )

  // Depois de um cadastro, a sugestão usada deixou de estar livre: volta a sugerir.
  const reiniciar = useCallback(() => {
    setSkuDigitado(null)
    setRodada((r) => r + 1)
  }, [])

  return { sku: skuDigitado ?? dados ?? '', editado, carregando, erro, alterarSku, reiniciar }
}
