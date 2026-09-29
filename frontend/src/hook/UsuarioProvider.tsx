import { useCallback, useMemo, useState, type ReactNode } from 'react'
import { FORMATO_USUARIO, definirUsuario } from '../middlewares/http/clienteOps.ts'
import { ContextoUsuario, type ValorUsuario } from './useUsuario.ts'

const CHAVE_ARMAZENAMENTO = 'ecommerce-ai.usuario'

function lerUsuarioSalvo(): string | null {
  try {
    const salvo = localStorage.getItem(CHAVE_ARMAZENAMENTO)
    return salvo !== null && FORMATO_USUARIO.test(salvo) ? salvo : null
  } catch {
    return null
  }
}

function salvarUsuario(usuario: string | null): void {
  try {
    if (usuario === null) localStorage.removeItem(CHAVE_ARMAZENAMENTO)
    else localStorage.setItem(CHAVE_ARMAZENAMENTO, usuario)
  } catch {
    // Armazenamento bloqueado (aba privada, política do navegador): o usuário só não é lembrado.
  }
}

export function UsuarioProvider({ children }: { children: ReactNode }) {
  // O middleware é atualizado junto com o estado, e não num useEffect, para que nenhuma
  // requisição disparada nos efeitos da primeira renderização saia sem X-Usuario.
  const [usuario, setUsuario] = useState<string | null>(() => {
    const salvo = lerUsuarioSalvo()
    definirUsuario(salvo)
    return salvo
  })

  const definir = useCallback((valor: string) => {
    const limpo = valor.trim()
    if (!FORMATO_USUARIO.test(limpo)) return false
    definirUsuario(limpo)
    salvarUsuario(limpo)
    setUsuario(limpo)
    return true
  }, [])

  const sair = useCallback(() => {
    definirUsuario(null)
    salvarUsuario(null)
    setUsuario(null)
  }, [])

  const valor = useMemo<ValorUsuario>(() => ({ usuario, definir, sair }), [usuario, definir, sair])

  return <ContextoUsuario value={valor}>{children}</ContextoUsuario>
}
