import { useState, type FormEvent } from 'react'
import { useCadastro } from '../../hook/useCadastro.ts'
import { Alerta } from '../comuns/Alerta.tsx'
import { Botao } from '../comuns/Botao.tsx'
import { Campo } from '../comuns/Campo.tsx'
import type { CupomProposta } from '../../middlewares/ops/tipos.ts'
import { ErrosFormulario } from './ErrosFormulario.tsx'
import { ehZero, hojeSaoPaulo, normalizarDecimal } from './formatacao.ts'
import { ListaAvisos } from './ListaAvisos.tsx'
import styles from './Formulario.module.css'

const CAMPOS = ['codigo', 'percentual_desconto', 'validade_inicio', 'validade_fim'] as const

interface FormCupomProps {
  proposta: CupomProposta | null
  interpretacaoId: string | null
  avisos: string[]
}

function formatarData(data: string): string {
  // Só reordena a string: um Date de data sem hora deslocaria o dia pelo fuso.
  const [ano, mes, dia] = data.split('-')
  return `${dia}/${mes}/${ano}`
}

export function FormCupom({ proposta, interpretacaoId, avisos }: FormCupomProps) {
  const [codigo, setCodigo] = useState(proposta?.codigo ?? '')
  const [percentual, setPercentual] = useState(proposta?.percentual_desconto?.replace('.', ',') ?? '')
  const [inicio, setInicio] = useState(proposta?.validade_inicio ?? hojeSaoPaulo())
  const [fim, setFim] = useState(proposta?.validade_fim ?? '')
  const [errosLocais, setErrosLocais] = useState<Record<string, string>>({})

  const { dados: criado, carregando, erro, executar } = useCadastro('cupom', interpretacaoId)
  const erroDe = (campo: string) => errosLocais[campo] ?? erro?.campos[campo] ?? null

  async function enviar(evento: FormEvent) {
    evento.preventDefault()
    const erros: Record<string, string> = {}
    const percentualNormalizado = normalizarDecimal(percentual)
    if (!/^[A-Z0-9_-]{3,30}$/.test(codigo)) {
      erros.codigo = 'Use de 3 a 30 caracteres: letras, números, _ ou -, sem espaços.'
    }
    if (percentualNormalizado === null) erros.percentual_desconto = 'Informe um percentual como 15 ou 12,5.'
    else if (ehZero(percentualNormalizado) || Number(percentualNormalizado) > 100) {
      erros.percentual_desconto = 'O percentual deve ser maior que 0 e no máximo 100.'
    }
    if (!inicio) erros.validade_inicio = 'Informe o início da validade.'
    if (!fim) erros.validade_fim = 'Informe o fim da validade.'
    // YYYY-MM-DD compara corretamente como texto.
    else if (inicio && fim < inicio) erros.validade_fim = 'O fim deve ser igual ou posterior ao início.'
    setErrosLocais(erros)
    if (Object.keys(erros).length > 0 || percentualNormalizado === null) return

    const resultado = await executar({
      codigo,
      percentual_desconto: percentualNormalizado,
      validade_inicio: inicio,
      validade_fim: fim,
    })
    if (resultado) {
      setCodigo('')
      setPercentual('')
      setInicio(hojeSaoPaulo())
      setFim('')
    }
  }

  return (
    <form onSubmit={enviar} noValidate className={styles.formulario} aria-labelledby="titulo-cupom">
      <h3 id="titulo-cupom" className={styles.titulo}>
        Cadastro de cupom
      </h3>
      {!criado && <ListaAvisos avisos={avisos} />}
      {criado && (
        <Alerta tipo="sucesso" titulo="Cupom cadastrado">
          <ul className={styles.criado}>
            <li>ID: {criado.id}</li>
            <li>
              {criado.codigo} — {criado.percentual_desconto.replace('.', ',')}% de desconto
            </li>
            <li>
              De {formatarData(criado.validade_inicio)} a {formatarData(criado.validade_fim)}
            </li>
          </ul>
        </Alerta>
      )}
      <ErrosFormulario erro={erro} camposExibidos={CAMPOS} />

      <div className={styles.linha}>
        <Campo rotulo="Código" obrigatorio erro={erroDe('codigo')}>
          {(c) => <input {...c} value={codigo} onChange={(e) => setCodigo(e.target.value.toUpperCase())} />}
        </Campo>
        <Campo rotulo="Desconto (%)" obrigatorio dica="Só desconto percentual." erro={erroDe('percentual_desconto')}>
          {(c) => (
            <input {...c} inputMode="decimal" value={percentual} onChange={(e) => setPercentual(e.target.value)} />
          )}
        </Campo>
      </div>
      <div className={styles.linha}>
        <Campo rotulo="Válido de" obrigatorio erro={erroDe('validade_inicio')}>
          {(c) => <input {...c} type="date" value={inicio} onChange={(e) => setInicio(e.target.value)} />}
        </Campo>
        <Campo rotulo="Válido até" obrigatorio erro={erroDe('validade_fim')}>
          {(c) => <input {...c} type="date" value={fim} min={inicio || undefined} onChange={(e) => setFim(e.target.value)} />}
        </Campo>
      </div>

      <div className={styles.acoes}>
        <Botao type="submit" carregando={carregando}>
          {carregando ? 'Cadastrando…' : 'Confirmar cadastro'}
        </Botao>
      </div>
    </form>
  )
}
