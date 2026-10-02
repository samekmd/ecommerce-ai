import { createContext, useContext } from 'react'

export interface ValorUsuario {
  usuario: string | null
  // Devolve false quando o valor não cabe no formato do X-Usuario; o usuário atual é mantido.
  definir: (usuario: string) => boolean
  sair: () => void
}

export const ContextoUsuario = createContext<ValorUsuario | null>(null)

// Único estado global da aplicação. Identifica quem fez a ação na auditoria; não é autenticação.
export function useUsuario(): ValorUsuario {
  const valor = useContext(ContextoUsuario)
  if (valor === null) throw new Error('useUsuario precisa estar dentro de <UsuarioProvider>')
  return valor
}
