import { useCallback, useEffect, useRef, useState } from 'react'
import { ErroApi, MENSAGEM_GENERICA } from '../middlewares/http/ErroApi.ts'

export interface EstadoRequisicao<A, T> {
  dados: T | null
  carregando: boolean
  erro: ErroApi | null
  // Devolve null em erro ou cancelamento; o erro fica em `erro`.
  executar: (args: A) => Promise<T | null>
  cancelar: () => void
  limpar: () => void
}

// Base dos hooks de caso de uso: guarda o AbortController da requisição corrente, descarta
// respostas de requisições substituídas e nunca transforma cancelamento em erro de tela.
export function useRequisicao<A, T>(
  fn: (args: A, signal: AbortSignal) => Promise<T>,
): EstadoRequisicao<A, T> {
  const [dados, setDados] = useState<T | null>(null)
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState<ErroApi | null>(null)
  const controlador = useRef<AbortController | null>(null)

  useEffect(() => () => controlador.current?.abort(), [])

  const executar = useCallback(
    async (args: A): Promise<T | null> => {
      controlador.current?.abort()
      const atual = new AbortController()
      controlador.current = atual
      setCarregando(true)
      setErro(null)
      try {
        const resultado = await fn(args, atual.signal)
        if (atual.signal.aborted) return null
        setDados(resultado)
        return resultado
      } catch (e) {
        if (atual.signal.aborted) return null
        setErro(e instanceof ErroApi ? e : new ErroApi(0, MENSAGEM_GENERICA))
        return null
      } finally {
        if (controlador.current === atual) {
          controlador.current = null
          setCarregando(false)
        }
      }
    },
    [fn],
  )

  const cancelar = useCallback(() => {
    controlador.current?.abort()
    controlador.current = null
    setCarregando(false)
  }, [])

  const limpar = useCallback(() => {
    cancelar()
    setDados(null)
    setErro(null)
  }, [cancelar])

  return { dados, carregando, erro, executar, cancelar, limpar }
}
