import { useState, type FormEvent, type KeyboardEvent } from 'react'
import { Botao } from '../comuns/Botao.tsx'
import { Campo } from '../comuns/Campo.tsx'
import styles from './Chat.module.css'

interface EntradaPerguntaProps {
  aoEnviar: (pergunta: string) => void
  // Uma pergunta por vez: desabilitada até a resposta anterior chegar.
  desabilitada: boolean
}

export function EntradaPergunta({ aoEnviar, desabilitada }: EntradaPerguntaProps) {
  const [texto, setTexto] = useState('')
  const pronta = texto.trim() !== '' && !desabilitada

  function enviar(evento?: FormEvent) {
    evento?.preventDefault()
    if (!pronta) return
    aoEnviar(texto.trim())
    setTexto('')
  }

  function aoTeclar(evento: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter envia; Shift+Enter quebra linha. Durante composição (IME) o Enter é do teclado.
    if (evento.key === 'Enter' && !evento.shiftKey && !evento.nativeEvent.isComposing) {
      evento.preventDefault()
      enviar()
    }
  }

  return (
    <form onSubmit={enviar} noValidate className={styles.entrada}>
      <Campo rotulo="Pergunta" dica="Enter envia · Shift+Enter quebra linha">
        {(c) => (
          <textarea
            {...c}
            rows={2}
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            onKeyDown={aoTeclar}
            placeholder="Ex.: Quantos pedidos foram feitos em 2025?"
            disabled={desabilitada}
          />
        )}
      </Campo>
      <Botao type="submit" disabled={!pronta}>
        Enviar
      </Botao>
    </form>
  )
}
