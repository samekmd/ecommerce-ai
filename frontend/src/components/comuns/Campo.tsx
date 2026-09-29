import { useId, type ReactNode } from 'react'
import styles from './Campo.module.css'

export interface PropsControle {
  id: string
  'aria-describedby': string | undefined
  'aria-invalid': boolean | undefined
  required: boolean | undefined
}

interface CampoProps {
  rotulo: string
  obrigatorio?: boolean
  dica?: string
  erro?: string | null
  // Render prop: o mesmo Campo serve para input, select, textarea ou um controle composto,
  // e o controle recebe o id e o aria-describedby que ligam rótulo, dica e erro a ele.
  children: (controle: PropsControle) => ReactNode
}

export function Campo({ rotulo, obrigatorio = false, dica, erro, children }: CampoProps) {
  const id = useId()
  const idDica = `${id}-dica`
  const idErro = `${id}-erro`
  const descritores = [dica ? idDica : null, erro ? idErro : null].filter(Boolean).join(' ')

  return (
    <div className={styles.campo}>
      <label htmlFor={id} className={styles.rotulo}>
        {rotulo}
        {obrigatorio && (
          <span className={styles.obrigatorio} aria-hidden="true">
            {' *'}
          </span>
        )}
      </label>
      {children({
        id,
        'aria-describedby': descritores || undefined,
        'aria-invalid': erro ? true : undefined,
        required: obrigatorio || undefined,
      })}
      {dica && (
        <p id={idDica} className={styles.dica}>
          {dica}
        </p>
      )}
      {erro && (
        <p id={idErro} className={styles.erro}>
          {erro}
        </p>
      )}
    </div>
  )
}
