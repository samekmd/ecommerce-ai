import { Alerta } from '../comuns/Alerta.tsx'

// Pontos que o agente pediu para conferir. Ficam em destaque, nunca escondidos.
export function ListaAvisos({ avisos }: { avisos: string[] }) {
  if (avisos.length === 0) return null
  return (
    <Alerta tipo="aviso" titulo="Confira antes de confirmar">
      <ul>
        {avisos.map((aviso, i) => (
          <li key={i}>{aviso}</li>
        ))}
      </ul>
    </Alerta>
  )
}
