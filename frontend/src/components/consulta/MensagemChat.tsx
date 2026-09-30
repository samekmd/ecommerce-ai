import type { Mensagem } from '../../hook/useConversa.ts'
import { Alerta } from '../comuns/Alerta.tsx'
import { Icone } from '../comuns/Icone.tsx'
import { RespostaMarkdown } from './RespostaMarkdown.tsx'
import styles from './Chat.module.css'

// O aviso de limite vira um alerta próprio; deixá-lo também no texto seria repetir a informação.
const AVISO_LIMITE = /\n*\[Limite de [^\]]*\]\s*$/

export function MensagemChat({ mensagem }: { mensagem: Mensagem }) {
  const doAgente = mensagem.autor === 'agente'
  return (
    <li className={`${styles.linha} ${doAgente ? styles.linhaAgente : styles.linhaUsuario}`}>
      <span className={`${styles.avatar} ${doAgente ? styles.avatarAgente : styles.avatarUsuario}`}>
        <Icone nome={doAgente ? 'agente' : 'usuario'} />
      </span>
      <div className={`${styles.balao} ${doAgente ? styles.balaoAgente : styles.balaoUsuario}`}>
        <span className="somente-leitor">{doAgente ? 'Agente:' : 'Você:'}</span>
        {doAgente ? (
          <RespostaMarkdown texto={mensagem.incompleta ? mensagem.texto.replace(AVISO_LIMITE, '') : mensagem.texto} />
        ) : (
          // Pergunta do usuário: texto puro, preservando as quebras de linha que ele digitou.
          <p className={styles.textoUsuario}>{mensagem.texto}</p>
        )}
        {mensagem.incompleta && (
          <Alerta tipo="aviso" titulo="Resposta possivelmente incompleta">
            O agente atingiu o limite de etapas antes de concluir. Tente uma pergunta mais específica.
          </Alerta>
        )}
      </div>
    </li>
  )
}
