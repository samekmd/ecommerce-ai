import { useState } from 'react'
import { useBuscaFornecedores } from '../../hook/useBuscaFornecedores.ts'
import { Botao } from '../comuns/Botao.tsx'
import type { PropsControle } from '../comuns/Campo.tsx'
import styles from './AutocompleteFornecedor.module.css'

export interface FornecedorEscolhido {
  id: number
  nome: string
}

interface AutocompleteFornecedorProps {
  controle: PropsControle
  selecionado: FornecedorEscolhido | null
  aoSelecionar: (fornecedor: FornecedorEscolhido | null) => void
  // fornecedor_citado da proposta: a busca já começa com ele.
  termoInicial: string
  aoCadastrarNovo: (nome: string) => void
}

export function AutocompleteFornecedor({
  controle,
  selecionado,
  aoSelecionar,
  termoInicial,
  aoCadastrarNovo,
}: AutocompleteFornecedorProps) {
  const [termo, setTermo] = useState(selecionado?.nome ?? termoInicial)
  const [aberto, setAberto] = useState(selecionado === null)
  const { dados, carregando, erro } = useBuscaFornecedores(aberto ? termo : '')
  const idResultados = `${controle.id}-resultados`

  function digitar(valor: string) {
    setTermo(valor)
    setAberto(true)
    // Mudar o texto desfaz a escolha: o que está no campo tem que ser o que vai ser gravado.
    if (selecionado) aoSelecionar(null)
  }

  return (
    <div className={styles.autocomplete}>
      <input
        {...controle}
        value={termo}
        onChange={(e) => digitar(e.target.value)}
        placeholder="Digite ao menos 2 letras do nome"
        autoComplete="off"
        aria-controls={idResultados}
      />
      {selecionado && (
        <p className={styles.selecionado}>
          Selecionado: <strong>{selecionado.nome}</strong> (#{selecionado.id})
        </p>
      )}
      <div id={idResultados} aria-live="polite">
        {aberto && carregando && <p className={styles.info}>Buscando…</p>}
        {aberto && erro && <p className={styles.erro}>{erro.message}</p>}
        {aberto && dados && dados.length > 0 && (
          <ul className={styles.resultados} aria-label={`${dados.length} fornecedor(es) encontrado(s)`}>
            {dados.map((f) => (
              <li key={f.id}>
                <button
                  type="button"
                  className={styles.opcao}
                  onClick={() => {
                    aoSelecionar({ id: f.id, nome: f.nome })
                    setTermo(f.nome)
                    setAberto(false)
                  }}
                >
                  <strong>{f.nome}</strong> — {f.cidade}/{f.estado}
                </button>
              </li>
            ))}
          </ul>
        )}
        {aberto && dados && dados.length === 0 && !carregando && (
          <div className={styles.vazio}>
            <p className={styles.info}>Nenhum fornecedor ativo encontrado com esse nome.</p>
            <Botao variante="secundario" onClick={() => aoCadastrarNovo(termo.trim())}>
              Cadastrar fornecedor “{termo.trim()}”
            </Botao>
          </div>
        )}
      </div>
    </div>
  )
}
