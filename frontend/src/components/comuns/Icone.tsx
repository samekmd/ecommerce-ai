import type { ReactNode } from 'react'
import styles from './Icone.module.css'

export type NomeIcone = 'usuario' | 'agente' | 'enviar' | 'nova-conversa'

// SVG inline em vez de lib de ícones: são quatro desenhos e não justificam dependência.
const DESENHOS: Record<NomeIcone, ReactNode> = {
  usuario: (
    <>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21c0-4.4 3.6-7 8-7s8 2.6 8 7" />
    </>
  ),
  agente: (
    <>
      <rect x="4" y="8" width="16" height="12" rx="3" />
      <path d="M12 4v4M2 13v3M22 13v3" />
      <circle cx="12" cy="3" r="1" />
      <circle cx="9" cy="14" r="1.25" fill="currentColor" />
      <circle cx="15" cy="14" r="1.25" fill="currentColor" />
    </>
  ),
  enviar: <path d="M4 12 20 4l-6 16-2.5-6.5z M11.5 13.5 20 4" />,
  'nova-conversa': (
    <>
      <path d="M4 5h16v11H9l-5 4z" />
      <path d="M12 8v5M9.5 10.5h5" />
    </>
  ),
}

export function Icone({ nome }: { nome: NomeIcone }) {
  // Decorativo: o texto ou aria-label de quem usa o ícone é que dá o significado.
  return (
    <svg className={styles.icone} viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      {DESENHOS[nome]}
    </svg>
  )
}
