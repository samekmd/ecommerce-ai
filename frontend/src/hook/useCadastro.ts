import { useCallback, useState } from 'react'
import { cadastrarCategoria } from '../middlewares/ops/categorias.ts'
import { cadastrarCupom } from '../middlewares/ops/cupons.ts'
import { cadastrarFornecedor } from '../middlewares/ops/fornecedores.ts'
import { cadastrarProduto } from '../middlewares/ops/produtos.ts'
import type { OpcoesCadastro } from '../middlewares/ops/tipos.ts'
import { useRequisicao } from './useRequisicao.ts'

// O formulário escolhe pelo tipo, sem precisar conhecer as funções de middlewares/.
const CADASTROS = {
  produto: cadastrarProduto,
  fornecedor: cadastrarFornecedor,
  categoria: cadastrarCategoria,
  cupom: cadastrarCupom,
}

type Cadastros = typeof CADASTROS
export type TipoCadastro = keyof Cadastros
type Dados<K extends TipoCadastro> = Parameters<Cadastros[K]>[0]
type Criado<K extends TipoCadastro> = Awaited<ReturnType<Cadastros[K]>>

// interpretacaoId é null no cadastro manual ou quando a auditoria da interpretação falhou.
export function useCadastro<K extends TipoCadastro>(tipo: K, interpretacaoId: string | null) {
  // Nasce com o formulário e sobrevive a 409/422: reenviar a mesma chave é o que impede gravar
  // duas vezes num duplo clique ou retry. Uma nova interpretação remonta o formulário (e o hook).
  const [chave, setChave] = useState(() => crypto.randomUUID())

  const enviar = useCallback(
    (dados: Dados<K>, signal: AbortSignal) => {
      // O TypeScript não correlaciona CADASTROS[tipo] com Dados<K>; o mapa acima garante o par.
      const cadastrar = CADASTROS[tipo] as (d: Dados<K>, o: OpcoesCadastro) => Promise<Criado<K>>
      return cadastrar(dados, { idempotencyKey: chave, interpretacaoId, signal })
    },
    [tipo, chave, interpretacaoId],
  )
  const { dados, carregando, erro, executar, limpar } = useRequisicao(enviar)

  const executarCadastro = useCallback(
    async (formulario: Dados<K>): Promise<Criado<K> | null> => {
      const criado = await executar(formulario)
      // Só um cadastro gravado consome a chave; o próximo registro precisa de outra.
      if (criado !== null) setChave(crypto.randomUUID())
      return criado
    },
    [executar],
  )

  return { dados, carregando, erro, executar: executarCadastro, limpar }
}
