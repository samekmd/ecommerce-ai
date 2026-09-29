import { useRef, useState, type ChangeEvent } from 'react'
import { Botao } from './Botao.tsx'
import { Campo } from './Campo.tsx'
import styles from './SeletorImagem.module.css'

const TIPOS_ACEITOS = ['image/jpeg', 'image/png', 'image/webp']
const TAMANHO_MAXIMO = 2 * 1024 * 1024

interface SeletorImagemProps {
  rotulo: string
  obrigatorio?: boolean
  // Data URL (resultado de readAsDataURL) ou null quando não há imagem.
  valor: string | null
  aoAlterar: (dataUrl: string | null) => void
  erro?: string | null
}

export function SeletorImagem({ rotulo, obrigatorio, valor, aoAlterar, erro }: SeletorImagemProps) {
  const [erroLocal, setErroLocal] = useState<string | null>(null)
  const entrada = useRef<HTMLInputElement>(null)

  function limparEntrada() {
    if (entrada.current) entrada.current.value = ''
  }

  function aoEscolher(evento: ChangeEvent<HTMLInputElement>) {
    const arquivo = evento.target.files?.[0]
    if (!arquivo) return
    // Valida antes de ler: não vale a pena carregar na memória um arquivo que será recusado.
    // O servidor revalida pelo conteúdo, então isto é conveniência, não segurança.
    if (!TIPOS_ACEITOS.includes(arquivo.type)) {
      setErroLocal('Use uma imagem JPEG, PNG ou WebP.')
      limparEntrada()
      return
    }
    if (arquivo.size > TAMANHO_MAXIMO) {
      setErroLocal('A imagem excede o tamanho máximo de 2 MB.')
      limparEntrada()
      return
    }
    setErroLocal(null)
    const leitor = new FileReader()
    leitor.onload = () => {
      if (typeof leitor.result === 'string') aoAlterar(leitor.result)
    }
    leitor.onerror = () => setErroLocal('Não foi possível ler o arquivo.')
    leitor.readAsDataURL(arquivo)
  }

  function remover() {
    setErroLocal(null)
    limparEntrada()
    aoAlterar(null)
  }

  return (
    <Campo rotulo={rotulo} obrigatorio={obrigatorio} dica="JPEG, PNG ou WebP, até 2 MB." erro={erroLocal ?? erro}>
      {(controle) => (
        <div className={styles.seletor}>
          <input
            {...controle}
            ref={entrada}
            type="file"
            accept={TIPOS_ACEITOS.join(',')}
            onChange={aoEscolher}
          />
          {valor && (
            <div className={styles.previa}>
              <img src={valor} alt="Prévia da imagem escolhida" />
              <Botao variante="secundario" onClick={remover}>
                Remover imagem
              </Botao>
            </div>
          )}
        </div>
      )}
    </Campo>
  )
}
