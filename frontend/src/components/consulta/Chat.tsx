import { useEffect, useRef } from 'react'
import type { Mensagem } from '../../hook/useConversa.ts'
import { Icone } from '../comuns/Icone.tsx'
import { EntradaPergunta } from './EntradaPergunta.tsx'
import { MensagemChat } from './MensagemChat.tsx'
import styles from './Chat.module.css'

const SUGESTOES = [
  'Quantos pedidos foram feitos em 2025?',
  'Quais os 5 produtos mais vendidos?',
  'Qual o faturamento por mês neste ano?',
]

interface ChatProps {
  mensagens: Mensagem[]
  carregando: boolean
  erro: string | null
  aoEnviar: (pergunta: string) => void
  aoNovaConversa: () => void
}

export function Chat({ mensagens, carregando, erro, aoEnviar, aoNovaConversa }: ChatProps) {
  const historico = useRef<HTMLDivElement>(null)
  const vazia = mensagens.length === 0 && !carregando && !erro

  // Rola só a área da conversa, sem mexer na rolagem da página.
  useEffect(() => {
    const el = historico.current
    if (el) el.scrollTop = el.scrollHeight
  }, [mensagens.length, carregando, erro])

  return (
    <section className={styles.chat} aria-labelledby="titulo-chat">
      <header className={styles.cabecalho}>
        <span className={`${styles.avatar} ${styles.avatarAgente}`}>
          <Icone nome="agente" />
        </span>
        <div className={styles.identificacao}>
          <h3 id="titulo-chat" className={styles.nome}>
            Assistente de consultas
          </h3>
          <p className={styles.subtitulo}>Só leitura: nenhuma pergunta altera os dados.</p>
        </div>
        <button
          type="button"
          className={styles.novaConversa}
          onClick={aoNovaConversa}
          disabled={mensagens.length === 0 && !carregando && !erro}
        >
          <Icone nome="nova-conversa" />
          Nova conversa
        </button>
      </header>

      <div ref={historico} className={styles.historico}>
        {vazia ? (
          <div className={styles.boasVindas}>
            <div className={`${styles.linha} ${styles.linhaAgente}`}>
              <span className={`${styles.avatar} ${styles.avatarAgente}`}>
                <Icone nome="agente" />
              </span>
              <div className={`${styles.balao} ${styles.balaoAgente}`}>
                Olá! Posso responder perguntas sobre pedidos, produtos, clientes e vendas da loja.
                Por onde quer começar?
              </div>
            </div>
            <ul className={styles.sugestoes} aria-label="Sugestões de pergunta">
              {SUGESTOES.map((s) => (
                <li key={s}>
                  <button type="button" className={styles.sugestao} onClick={() => aoEnviar(s)}>
                    {s}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <ol role="log" aria-live="polite" aria-label="Mensagens da conversa" className={styles.mensagens}>
            {mensagens.map((m) => (
              <MensagemChat key={m.id} mensagem={m} />
            ))}
            {carregando && (
              <li className={`${styles.linha} ${styles.linhaAgente}`}>
                <span className={`${styles.avatar} ${styles.avatarAgente}`}>
                  <Icone nome="agente" />
                </span>
                <div className={`${styles.balao} ${styles.balaoAgente}`} role="status">
                  <span className={styles.digitando} aria-hidden="true">
                    <span />
                    <span />
                    <span />
                  </span>
                  <span className="somente-leitor">O agente está consultando os dados. Pode levar mais de um minuto.</span>
                </div>
              </li>
            )}
            {erro && (
              <li className={`${styles.linha} ${styles.linhaAgente}`}>
                <span className={`${styles.avatar} ${styles.avatarAgente}`}>
                  <Icone nome="agente" />
                </span>
                <div className={`${styles.balao} ${styles.balaoErro}`} role="alert">
                  {erro}
                </div>
              </li>
            )}
          </ol>
        )}
      </div>

      <EntradaPergunta aoEnviar={aoEnviar} desabilitada={carregando} />
    </section>
  )
}
