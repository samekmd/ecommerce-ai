import styles from './Carregando.module.css'

export function Carregando({ mensagem = 'Carregando…' }: { mensagem?: string }) {
  return (
    <div role="status" aria-live="polite" className={styles.carregando}>
      <span className={styles.spinner} aria-hidden="true" />
      {mensagem}
    </div>
  )
}
