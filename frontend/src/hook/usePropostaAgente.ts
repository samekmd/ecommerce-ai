import { useCallback, useRef, useState } from 'react'
import type {
  CategoriaProposta,
  CupomProposta,
  FornecedorProposta,
  PedidoEsclarecimento,
  ProdutoProposta,
  RespostaInterpretar,
} from '../middlewares/ops/tipos.ts'

// proposta null = cadastro manual, formulário vazio.
export type ConteudoFormulario =
  | { tipo: 'produto'; proposta: ProdutoProposta | null }
  | { tipo: 'fornecedor'; proposta: FornecedorProposta | null }
  | { tipo: 'categoria'; proposta: CategoriaProposta | null }
  | { tipo: 'cupom'; proposta: CupomProposta | null }

export type TipoFormulario = ConteudoFormulario['tipo']

// `chave` muda a cada abertura e vira a key do formulário: remontar é o que gera uma
// Idempotency-Key nova para cada interpretação ou cadastro manual.
export type FormularioAberto = ConteudoFormulario & { interpretacaoId: string | null; avisos: string[]; chave: number }

// Guarda a proposta do agente entre a tela de iteração e a página do formulário. Vive em memória
// enquanto a aba Cadastro estiver montada: não há estado global além de useUsuario.
export function usePropostaAgente() {
  const [aberto, setAberto] = useState<FormularioAberto | null>(null)
  const [esclarecimento, setEsclarecimento] = useState<PedidoEsclarecimento | null>(null)
  const [ultimaFrase, setUltimaFrase] = useState('')
  const contador = useRef(0)

  const abrir = useCallback(
    (conteudo: ConteudoFormulario, interpretacaoId: string | null = null, avisos: string[] = []) => {
      contador.current += 1
      setAberto({ ...conteudo, interpretacaoId, avisos, chave: contador.current })
    },
    [],
  )

  const receber = useCallback(
    (resposta: RespostaInterpretar, frase: string) => {
      setUltimaFrase(frase)
      // Esclarecimento não tem formulário: o usuário fica na iteração para reformular a frase.
      if (resposta.tipo === 'esclarecimento') {
        setEsclarecimento(resposta.proposta)
        return
      }
      setEsclarecimento(null)
      const { interpretacao_id, avisos, ...conteudo } = resposta
      abrir(conteudo, interpretacao_id, avisos)
    },
    [abrir],
  )

  const descartar = useCallback(() => setAberto(null), [])

  return { aberto, esclarecimento, ultimaFrase, receber, abrir, descartar }
}
