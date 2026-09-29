import { useEffect, useRef } from 'react'
import type { Mensagem } from '../../hook/useConversa.ts'
import { Alerta } from '../comuns/Alerta.tsx'
import { Botao } from '../comuns/Botao.tsx'
import { Carregando } from '../comuns/Carregando.tsx'
import { EntradaPergunta } from './EntradaPergunta.tsx'
import { MensagemChat } from './MensagemChat.tsx'
import styles from './Chat.module.css'

interface ChatProps {
  mensagens: Mensagem[]
  carregando: boolean
  erro: string | null
  aoEnviar: (pergunta: string) => void
  aoNovaConversa: () => void
}

export function Chat({ mensagens, carregando, erro, aoEnviar, aoNovaConversa }: ChatProps) {
  const fim = useRef<HTMLDivElement>(null)

  useEffect(() => {
    fim.current?.scrollIntoView?.({ behavior: 'smooth', block: 'end' })
  }, [mensagens.length, carregando])

  return (
    <section className={styles.chat} aria-label="Conversa com o agente de consultas">
      <div className={styles.cabecalho}>
        <p className={styles.explicacao}>Pergunte sobre os dados da loja. Só leitura: nada é alterado.</p>
        <Botao variante="secundario" onClick={aoNovaConversa} disabled={mensagens.length === 0 && !carregando}>
          Nova conversa
        </Botao>
      </div>
      {mensagens.length > 0 && (
        <ol role="log" aria-live="polite" className={styles.mensagens}>
          {mensagens.map((m) => (
            <MensagemChat key={m.id} mensagem={m} />
          ))}
        </ol>
      )}
      {carregando && <Carregando mensagem="Consultando… pode levar mais de um minuto." />}
      {erro && <Alerta tipo="erro">{erro}</Alerta>}
      <div ref={fim} />
      <EntradaPergunta aoEnviar={aoEnviar} desabilitada={carregando} />
    </section>
  )
}
