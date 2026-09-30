import { useEffect, useId, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { Icone } from '../comuns/Icone.tsx'
import styles from './Chat.module.css'

interface EntradaPerguntaProps {
  aoEnviar: (pergunta: string) => void
  // Uma pergunta por vez: desabilitada até a resposta anterior chegar.
  desabilitada: boolean
}

export function EntradaPergunta({ aoEnviar, desabilitada }: EntradaPerguntaProps) {
  const [texto, setTexto] = useState('')
  const campo = useRef<HTMLTextAreaElement>(null)
  const id = useId()
  const pronta = texto.trim() !== '' && !desabilitada

  // Cresce com o texto até o max-height do CSS; depois rola.
  useEffect(() => {
    const el = campo.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight}px`
  }, [texto])

  // Ao liberar a entrada depois da resposta, o foco volta para continuar a conversa.
  useEffect(() => {
    if (!desabilitada) campo.current?.focus()
  }, [desabilitada])

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
      <label htmlFor={id} className="somente-leitor">
        Pergunta
      </label>
      <textarea
        id={id}
        ref={campo}
        rows={1}
        value={texto}
        onChange={(e) => setTexto(e.target.value)}
        onKeyDown={aoTeclar}
        placeholder={desabilitada ? 'Aguardando a resposta…' : 'Pergunte sobre os dados da loja…'}
        disabled={desabilitada}
        aria-describedby={`${id}-dica`}
        className={styles.campoPergunta}
      />
      <span id={`${id}-dica`} className="somente-leitor">
        Enter envia, Shift+Enter quebra linha.
      </span>
      <button type="submit" className={styles.enviar} disabled={!pronta} aria-label="Enviar pergunta">
        <Icone nome="enviar" />
      </button>
    </form>
  )
}
