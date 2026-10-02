import { useEffect, useRef } from 'react'
import { Botao } from '../components/comuns/Botao.tsx'
import { FormCategoria } from '../components/cadastro/FormCategoria.tsx'
import { FormCupom } from '../components/cadastro/FormCupom.tsx'
import { FormFornecedor } from '../components/cadastro/FormFornecedor.tsx'
import { FormProduto } from '../components/cadastro/FormProduto.tsx'
import { useCategorias } from '../hook/useCategorias.ts'
import type { ConteudoFormulario, FormularioAberto, TipoFormulario } from '../hook/usePropostaAgente.ts'
import type { CategoriaResumo } from '../middlewares/ops/tipos.ts'
import styles from './FormularioCadastroPage.module.css'

const MANUAIS: { tipo: TipoFormulario; rotulo: string }[] = [
  { tipo: 'produto', rotulo: 'Produto' },
  { tipo: 'fornecedor', rotulo: 'Fornecedor' },
  { tipo: 'categoria', rotulo: 'Categoria' },
  { tipo: 'cupom', rotulo: 'Cupom' },
]

interface FormularioCadastroPageProps {
  aberto: FormularioAberto
  aoVoltar: () => void
  aoAbrir: (conteudo: ConteudoFormulario) => void
}

export function FormularioCadastroPage({ aberto, aoVoltar, aoAbrir }: FormularioCadastroPageProps) {
  const categorias = useCategorias()
  const titulo = useRef<HTMLHeadingElement>(null)

  // A troca de tela não muda a URL; mover o foco é o que avisa o leitor de tela.
  useEffect(() => {
    titulo.current?.focus()
  }, [])

  return (
    <>
      <div className={styles.topo}>
        <h2 ref={titulo} tabIndex={-1} className={styles.titulo}>
          Revisar cadastro
        </h2>
        <Botao variante="secundario" onClick={aoVoltar}>
          ← Voltar
        </Botao>
      </div>
      <div className={styles.manual} role="group" aria-label="Cadastrar outro tipo">
        <span>Cadastrar outro tipo:</span>
        {MANUAIS.map(({ tipo, rotulo }) => (
          <Botao key={tipo} variante="secundario" onClick={() => aoAbrir({ tipo, proposta: null })}>
            {rotulo}
          </Botao>
        ))}
      </div>
      {categorias.erro && (aberto.tipo === 'produto' || aberto.tipo === 'categoria') && (
        <p className={styles.aviso}>
          Não foi possível carregar as categorias: {categorias.erro.message}{' '}
          <Botao variante="secundario" onClick={() => void categorias.recarregar()}>
            Tentar de novo
          </Botao>
        </p>
      )}
      <div className={styles.painel}>
        {renderizar(aberto, categorias.dados, () => void categorias.recarregar(), (nome) =>
          aoAbrir({
            tipo: 'fornecedor',
            proposta: { nome, cnpj: null, email_contato: null, telefone: null, cidade: null, estado: null, avisos: [] },
          }),
        )}
      </div>
    </>
  )
}

function renderizar(
  aberto: FormularioAberto,
  categorias: CategoriaResumo[] | null,
  recarregarCategorias: () => void,
  abrirFornecedor: (nome: string) => void,
) {
  const { interpretacaoId, avisos, chave } = aberto
  switch (aberto.tipo) {
    case 'produto':
      return (
        <FormProduto
          key={chave}
          proposta={aberto.proposta}
          interpretacaoId={interpretacaoId}
          avisos={avisos}
          categorias={categorias}
          aoCadastrarFornecedor={abrirFornecedor}
        />
      )
    case 'fornecedor':
      return <FormFornecedor key={chave} proposta={aberto.proposta} interpretacaoId={interpretacaoId} avisos={avisos} />
    case 'categoria':
      return (
        <FormCategoria
          key={chave}
          proposta={aberto.proposta}
          interpretacaoId={interpretacaoId}
          avisos={avisos}
          categorias={categorias}
          aoCriada={recarregarCategorias}
        />
      )
    case 'cupom':
      return <FormCupom key={chave} proposta={aberto.proposta} interpretacaoId={interpretacaoId} avisos={avisos} />
    default: {
      // Um tipo novo na API sem formulário aqui quebra a compilação.
      const naoTratado: never = aberto
      return naoTratado
    }
  }
}
