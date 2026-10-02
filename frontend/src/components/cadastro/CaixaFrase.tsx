import { useState, type FormEvent } from 'react'
import { Alerta } from '../comuns/Alerta.tsx'
import { Botao } from '../comuns/Botao.tsx'
import { Campo } from '../comuns/Campo.tsx'

const MAXIMO = 1000

interface CaixaFraseProps {
  // Ao voltar do formulário, a frase anterior reaparece para ser ajustada.
  fraseInicial?: string
  aoInterpretar: (mensagem: string) => void
  carregando: boolean
  erro: string | null
}

export function CaixaFrase({ fraseInicial = '', aoInterpretar, carregando, erro }: CaixaFraseProps) {
  const [frase, setFrase] = useState(fraseInicial)
  const limpa = frase.trim()

  function enviar(evento: FormEvent) {
    evento.preventDefault()
    if (limpa && !carregando) aoInterpretar(limpa)
  }

  return (
    <form onSubmit={enviar} noValidate>
      <Campo
        rotulo="O que você quer cadastrar?"
        dica={`Ex.: "Cadastre 5 camisas da Nike a 100 reais, fornecedor Casa 1". ${frase.length}/${MAXIMO}`}
      >
        {(controle) => (
          <textarea
            {...controle}
            rows={3}
            maxLength={MAXIMO}
            value={frase}
            onChange={(e) => setFrase(e.target.value)}
            disabled={carregando}
          />
        )}
      </Campo>
      <Botao type="submit" carregando={carregando} disabled={!limpa}>
        Interpretar
      </Botao>
      {erro && <Alerta tipo="erro">{erro}</Alerta>}
    </form>
  )
}
