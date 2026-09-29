import { useState, type FormEvent } from 'react'
import { useUsuario } from '../../hook/useUsuario.ts'
import { Botao } from '../comuns/Botao.tsx'
import { Campo } from '../comuns/Campo.tsx'
import styles from './IdentificacaoUsuario.module.css'

// Identifica quem cadastra, para a auditoria (X-Usuario). Não é login: não há senha.
export function IdentificacaoUsuario() {
  const { usuario, definir, sair } = useUsuario()
  const [texto, setTexto] = useState('')
  const [erro, setErro] = useState<string | null>(null)

  if (usuario) {
    return (
      <div className={styles.identificado}>
        <span>
          Cadastrando como <strong>{usuario}</strong>
        </span>
        <Botao variante="secundario" onClick={sair}>
          Trocar usuário
        </Botao>
      </div>
    )
  }

  function entrar(evento: FormEvent) {
    evento.preventDefault()
    if (definir(texto)) {
      setTexto('')
      setErro(null)
    } else {
      setErro('Use de 1 a 100 caracteres: letras sem acento, números, ponto, _, @ ou -.')
    }
  }

  return (
    <form onSubmit={entrar} noValidate className={styles.formulario}>
      <Campo
        rotulo="Seu usuário"
        obrigatorio
        dica="Registrado na auditoria de cada cadastro."
        erro={erro}
      >
        {(controle) => (
          <input {...controle} value={texto} onChange={(e) => setTexto(e.target.value)} autoComplete="username" />
        )}
      </Campo>
      <Botao type="submit">Entrar</Botao>
    </form>
  )
}
