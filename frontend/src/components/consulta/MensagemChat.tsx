import type { Mensagem } from '../../hook/useConversa.ts'
import { Alerta } from '../comuns/Alerta.tsx'
import styles from './Chat.module.css'

export function MensagemChat({ mensagem }: { mensagem: Mensagem }) {
  const doAgente = mensagem.autor === 'agente'
  return (
    <li className={`${styles.mensagem} ${doAgente ? styles.agente : styles.usuario}`}>
      <span className={styles.autor}>{doAgente ? 'Agente' : 'Você'}</span>
      {/* Texto do LLM, possivelmente markdown: renderizado como texto puro, nunca como HTML. */}
      <p className={styles.texto}>{mensagem.texto}</p>
      {mensagem.incompleta && (
        <Alerta tipo="aviso" titulo="Resposta possivelmente incompleta">
          O agente atingiu o limite de etapas antes de concluir. Tente uma pergunta mais específica.
        </Alerta>
      )}
    </li>
  )
}
