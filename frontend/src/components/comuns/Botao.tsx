import type { ButtonHTMLAttributes } from 'react'
import styles from './Botao.module.css'

interface BotaoProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variante?: 'primario' | 'secundario'
  // Desabilita enquanto a ação anterior não termina, para evitar envio duplo.
  carregando?: boolean
}

export function Botao({
  variante = 'primario',
  carregando = false,
  type = 'button',
  disabled,
  className,
  children,
  ...resto
}: BotaoProps) {
  return (
    <button
      {...resto}
      type={type}
      disabled={disabled || carregando}
      aria-busy={carregando || undefined}
      className={[styles.botao, styles[variante], className].filter(Boolean).join(' ')}
    >
      {children}
    </button>
  )
}
