import { Alerta } from '../comuns/Alerta.tsx'
import type { ErroApi } from '../../middlewares/ops/tipos.ts'

interface ErrosFormularioProps {
  erro: ErroApi | null
  // Campos que o formulário já mostra junto do controle; os demais aparecem aqui.
  camposExibidos: readonly string[]
}

const ROTULOS: Record<string, string> = { 'X-Usuario': 'Usuário' }

// Nenhum erro pode sumir: o que não tem campo na tela (geral, X-Usuario, campo inesperado)
// vai para um alerta no topo do formulário.
export function ErrosFormulario({ erro, camposExibidos }: ErrosFormularioProps) {
  if (!erro) return null
  const soltos = Object.entries(erro.campos).filter(([campo]) => !camposExibidos.includes(campo))
  if (!erro.geral && soltos.length === 0) {
    return <Alerta tipo="erro">Corrija os campos destacados.</Alerta>
  }
  return (
    <Alerta tipo="erro" titulo="Não foi possível cadastrar">
      {erro.geral && <p>{erro.geral}</p>}
      {soltos.length > 0 && (
        <ul>
          {soltos.map(([campo, mensagem]) => (
            <li key={campo}>
              {ROTULOS[campo] ?? campo}: {mensagem}
            </li>
          ))}
        </ul>
      )}
    </Alerta>
  )
}
