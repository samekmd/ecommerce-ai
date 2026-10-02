import type { ReactNode } from 'react'
import styles from './Alerta.module.css'

interface AlertaProps {
  tipo: 'erro' | 'aviso' | 'sucesso' | 'info'
  titulo?: string
  children: ReactNode
}

export function Alerta({ tipo, titulo, children }: AlertaProps) {
  // Só erro interrompe o leitor de tela; os demais são anunciados sem pressa.
  return (
    <div role={tipo === 'erro' ? 'alert' : 'status'} className={`${styles.alerta} ${styles[tipo]}`}>
      {titulo && <p className={styles.titulo}>{titulo}</p>}
      <div>{children}</div>
    </div>
  )
}
