import { useEffect, useRef, type SyntheticEvent } from 'react'
import { Botao } from '../comuns/Botao.tsx'
import styles from './ModalAguardandoAgente.module.css'

interface ModalAguardandoAgenteProps {
  aberto: boolean
  aoCancelar: () => void
}

// <dialog> com showModal() dá foco preso e fundo inerte sem dependência nova. Fica sempre montado
// para o efeito conseguir abrir e fechar o mesmo elemento.
export function ModalAguardandoAgente({ aberto, aoCancelar }: ModalAguardandoAgenteProps) {
  const dialogo = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const elemento = dialogo.current
    if (!elemento) return
    if (aberto && !elemento.open) elemento.showModal()
    else if (!aberto && elemento.open) elemento.close()
  }, [aberto])

  // Esc cancela a interpretação; quem fecha o diálogo é o efeito, quando `aberto` vira false.
  function cancelar(evento: SyntheticEvent) {
    evento.preventDefault()
    aoCancelar()
  }

  return (
    <dialog ref={dialogo} className={styles.modal} aria-labelledby="titulo-aguardando-agente" onCancel={cancelar}>
      <div className={styles.conteudo}>
        <span className={styles.spinner} aria-hidden="true" />
        <div role="status" aria-live="polite">
          <p id="titulo-aguardando-agente" className={styles.titulo}>
            {aberto ? 'Preparando o cadastro…' : ''}
          </p>
          <p className={styles.dica}>{aberto ? 'O agente está interpretando a frase. Pode levar até 1 minuto.' : ''}</p>
        </div>
        <Botao variante="secundario" onClick={aoCancelar}>
          Cancelar
        </Botao>
      </div>
    </dialog>
  )
}
