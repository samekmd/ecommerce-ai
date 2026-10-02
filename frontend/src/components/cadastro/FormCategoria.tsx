import { useState, type FormEvent } from 'react'
import { useCadastro } from '../../hook/useCadastro.ts'
import { Alerta } from '../comuns/Alerta.tsx'
import { Botao } from '../comuns/Botao.tsx'
import { Campo } from '../comuns/Campo.tsx'
import type { CategoriaProposta, CategoriaResumo } from '../../middlewares/ops/tipos.ts'
import { ErrosFormulario } from './ErrosFormulario.tsx'
import { ListaAvisos } from './ListaAvisos.tsx'
import { SelectCategoria } from './SelectCategoria.tsx'
import styles from './Formulario.module.css'

const CAMPOS = ['nome', 'categoria_pai_id'] as const

interface FormCategoriaProps {
  proposta: CategoriaProposta | null
  interpretacaoId: string | null
  avisos: string[]
  categorias: CategoriaResumo[] | null
  // A lista de categorias da página fica desatualizada depois de um cadastro.
  aoCriada: () => void
}

export function FormCategoria({ proposta, interpretacaoId, avisos, categorias, aoCriada }: FormCategoriaProps) {
  const [nome, setNome] = useState(proposta?.nome ?? '')
  const [paiId, setPaiId] = useState<number | null>(proposta?.categoria_pai_id ?? null)
  const [errosLocais, setErrosLocais] = useState<Record<string, string>>({})

  const { dados: criada, carregando, erro, executar } = useCadastro('categoria', interpretacaoId)
  const erroDe = (campo: string) => errosLocais[campo] ?? erro?.campos[campo] ?? null
  const caminhoPai = categorias?.find((c) => c.id === criada?.categoria_pai_id)?.caminho

  async function enviar(evento: FormEvent) {
    evento.preventDefault()
    const erros: Record<string, string> = {}
    if (!nome.trim()) erros.nome = 'Informe o nome.'
    setErrosLocais(erros)
    if (Object.keys(erros).length > 0) return

    const resultado = await executar({ nome: nome.trim(), categoria_pai_id: paiId })
    if (resultado) {
      setNome('')
      setPaiId(null)
      aoCriada()
    }
  }

  return (
    <form onSubmit={enviar} noValidate className={styles.formulario} aria-labelledby="titulo-categoria">
      <h3 id="titulo-categoria" className={styles.titulo}>
        Cadastro de categoria
      </h3>
      {!criada && <ListaAvisos avisos={avisos} />}
      {criada && (
        <Alerta tipo="sucesso" titulo="Categoria cadastrada">
          <ul className={styles.criado}>
            <li>ID: {criada.id}</li>
            <li>
              {caminhoPai ? `${caminhoPai} > ` : ''}
              {criada.nome}
            </li>
          </ul>
        </Alerta>
      )}
      <ErrosFormulario erro={erro} camposExibidos={CAMPOS} />

      <Campo rotulo="Nome" obrigatorio erro={erroDe('nome')}>
        {(c) => <input {...c} value={nome} onChange={(e) => setNome(e.target.value)} />}
      </Campo>
      <Campo rotulo="Categoria pai" erro={erroDe('categoria_pai_id')}>
        {(c) => (
          <SelectCategoria
            controle={c}
            categorias={categorias}
            valor={paiId}
            aoAlterar={setPaiId}
            rotuloVazio="Nenhuma — categoria raiz"
          />
        )}
      </Campo>

      <div className={styles.acoes}>
        <Botao type="submit" carregando={carregando}>
          {carregando ? 'Cadastrando…' : 'Confirmar cadastro'}
        </Botao>
      </div>
    </form>
  )
}
