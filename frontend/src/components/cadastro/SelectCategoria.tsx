import type { PropsControle } from '../comuns/Campo.tsx'
import type { CategoriaResumo } from '../../middlewares/ops/tipos.ts'

interface SelectCategoriaProps {
  controle: PropsControle
  categorias: CategoriaResumo[] | null
  valor: number | null
  aoAlterar: (id: number | null) => void
  rotuloVazio: string
  // Produto deve ir para uma categoria final; categoria pai pode ser qualquer uma.
  destacarFolhas?: boolean
}

export function SelectCategoria({
  controle,
  categorias,
  valor,
  aoAlterar,
  rotuloVazio,
  destacarFolhas = false,
}: SelectCategoriaProps) {
  const lista = categorias ?? []
  const opcao = (c: CategoriaResumo) => (
    <option key={c.id} value={c.id}>
      {c.caminho}
    </option>
  )

  return (
    <select
      {...controle}
      value={valor ?? ''}
      onChange={(e) => aoAlterar(e.target.value === '' ? null : Number(e.target.value))}
      disabled={categorias === null}
    >
      <option value="">{categorias === null ? 'Carregando categorias…' : rotuloVazio}</option>
      {destacarFolhas ? (
        <>
          <optgroup label="Categorias finais (recomendadas)">{lista.filter((c) => c.folha).map(opcao)}</optgroup>
          <optgroup label="Categorias com subcategorias">{lista.filter((c) => !c.folha).map(opcao)}</optgroup>
        </>
      ) : (
        lista.map(opcao)
      )}
    </select>
  )
}
