import { useCallback, useRef, useState } from 'react'
import { perguntar } from '../middlewares/query/perguntas.ts'
import { useRequisicao } from './useRequisicao.ts'

export interface Mensagem {
  id: string
  autor: 'usuario' | 'agente'
  // Texto do LLM: exibir como texto (pre-wrap), nunca como HTML.
  texto: string
  // O agente atingiu o limite de iterações e avisou que a resposta pode estar incompleta.
  incompleta: boolean
}

const CHAVE_THREAD = 'consulta.thread_id'
const AVISO_LIMITE = /\[Limite de [^\]]*\]\s*$/

function lerThread(): string | null {
  try {
    return sessionStorage.getItem(CHAVE_THREAD)
  } catch {
    return null
  }
}

function salvarThread(threadId: string | null): void {
  try {
    if (threadId === null) sessionStorage.removeItem(CHAVE_THREAD)
    else sessionStorage.setItem(CHAVE_THREAD, threadId)
  } catch {
    // Sem sessionStorage a conversa só não sobrevive a um recarregamento da página.
  }
}

const enviarPergunta = (
  { pergunta, threadId }: { pergunta: string; threadId: string | null },
  signal: AbortSignal,
) => perguntar(pergunta, threadId, signal)

export function useConversa() {
  const { carregando, erro, executar, limpar } = useRequisicao(enviarPergunta)
  const [mensagens, setMensagens] = useState<Mensagem[]>([])
  const [threadId, setThreadId] = useState<string | null>(lerThread)
  // O estado `carregando` só muda no próximo render; a ref barra um segundo envio no mesmo clique.
  const emAndamento = useRef<object | null>(null)

  const enviar = useCallback(
    async (texto: string) => {
      const pergunta = texto.trim()
      // Uma pergunta por vez: duas no mesmo thread_id confundem o histórico do agente.
      if (pergunta === '' || emAndamento.current !== null) return
      const esta = {}
      emAndamento.current = esta
      setMensagens((atuais) => [
        ...atuais,
        { id: crypto.randomUUID(), autor: 'usuario', texto: pergunta, incompleta: false },
      ])
      try {
        const resposta = await executar({ pergunta, threadId })
        if (resposta === null) return
        salvarThread(resposta.thread_id)
        setThreadId(resposta.thread_id)
        setMensagens((atuais) => [
          ...atuais,
          {
            id: crypto.randomUUID(),
            autor: 'agente',
            texto: resposta.resposta,
            incompleta: AVISO_LIMITE.test(resposta.resposta),
          },
        ])
      } finally {
        if (emAndamento.current === esta) emAndamento.current = null
      }
    },
    [executar, threadId],
  )

  const novaConversa = useCallback(() => {
    limpar()
    emAndamento.current = null
    salvarThread(null)
    setThreadId(null)
    setMensagens([])
  }, [limpar])

  return { mensagens, carregando, erro, enviar, novaConversa }
}
