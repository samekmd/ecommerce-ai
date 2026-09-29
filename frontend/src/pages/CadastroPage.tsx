import { useState } from 'react'
import { Botao } from '../components/comuns/Botao.tsx'
import { CaixaFrase } from '../components/cadastro/CaixaFrase.tsx'
import { CardEsclarecimento } from '../components/cadastro/CardEsclarecimento.tsx'
import { FormCategoria } from '../components/cadastro/FormCategoria.tsx'
import { FormCupom } from '../components/cadastro/FormCupom.tsx'
import { FormFornecedor } from '../components/cadastro/FormFornecedor.tsx'
import { FormProduto } from '../components/cadastro/FormProduto.tsx'
import { IdentificacaoUsuario } from '../components/cadastro/IdentificacaoUsuario.tsx'
import { useCategorias } from '../hook/useCategorias.ts'
import { useInterpretar } from '../hook/useInterpretar.ts'
import { useUsuario } from '../hook/useUsuario.ts'
import type {
  CategoriaProposta,
  CategoriaResumo,
  CupomProposta,
  FornecedorProposta,
  PedidoEsclarecimento,
  ProdutoProposta,
} from '../middlewares/ops/tipos.ts'
import styles from './CadastroPage.module.css'

// proposta null = cadastro manual, formulário vazio.
type Conteudo =
  | { tipo: 'produto'; proposta: ProdutoProposta | null }
  | { tipo: 'fornecedor'; proposta: FornecedorProposta | null }
  | { tipo: 'categoria'; proposta: CategoriaProposta | null }
  | { tipo: 'cupom'; proposta: CupomProposta | null }
  | { tipo: 'esclarecimento'; proposta: PedidoEsclarecimento }

// `chave` muda a cada abertura e vira a key do formulário: remontar é o que gera uma
// Idempotency-Key nova para cada interpretação ou cadastro manual.
type Aberto = Conteudo & { interpretacaoId: string | null; avisos: string[]; chave: number }

type TipoManual = Exclude<Conteudo['tipo'], 'esclarecimento'>

const MANUAIS: { tipo: TipoManual; rotulo: string }[] = [
  { tipo: 'produto', rotulo: 'Produto' },
  { tipo: 'fornecedor', rotulo: 'Fornecedor' },
  { tipo: 'categoria', rotulo: 'Categoria' },
  { tipo: 'cupom', rotulo: 'Cupom' },
]

export function CadastroPage() {
  const { usuario } = useUsuario()
  return (
    <>
      <h2>Cadastro</h2>
      <IdentificacaoUsuario />
      {/* Sem usuário o backend recusa o cadastro (X-Usuario é obrigatório). */}
      {usuario && <AreaCadastro />}
    </>
  )
}

function AreaCadastro() {
  const interpretacao = useInterpretar()
  const categorias = useCategorias()
  const [aberto, setAberto] = useState<Aberto | null>(null)
  const [contador, setContador] = useState(0)

  function abrir(conteudo: Conteudo, interpretacaoId: string | null = null, avisos: string[] = []) {
    const chave = contador + 1
    setContador(chave)
    setAberto({ ...conteudo, interpretacaoId, avisos, chave })
  }

  async function interpretar(mensagem: string) {
    const resposta = await interpretacao.executar(mensagem)
    if (resposta) abrir(resposta, resposta.interpretacao_id, resposta.avisos)
  }

  return (
    <>
      <CaixaFrase
        aoInterpretar={(m) => void interpretar(m)}
        carregando={interpretacao.carregando}
        erro={interpretacao.erro?.message ?? null}
      />
      <div className={styles.manual} role="group" aria-label="Cadastro manual">
        <span>Ou preencha sem interpretar:</span>
        {MANUAIS.map(({ tipo, rotulo }) => (
          <Botao key={tipo} variante="secundario" onClick={() => abrir({ tipo, proposta: null })}>
            {rotulo}
          </Botao>
        ))}
      </div>
      {categorias.erro && tipoUsaCategorias(aberto) && (
        <p className={styles.aviso}>
          Não foi possível carregar as categorias: {categorias.erro.message}{' '}
          <Botao variante="secundario" onClick={() => void categorias.recarregar()}>
            Tentar de novo
          </Botao>
        </p>
      )}
      {aberto && (
        <div className={styles.painel}>
          {renderizar(aberto, categorias.dados, () => void categorias.recarregar(), (nome) =>
            abrir({
              tipo: 'fornecedor',
              proposta: { nome, cnpj: null, email_contato: null, telefone: null, cidade: null, estado: null, avisos: [] },
            }),
          )}
        </div>
      )}
    </>
  )
}

function tipoUsaCategorias(aberto: Aberto | null): boolean {
  return aberto?.tipo === 'produto' || aberto?.tipo === 'categoria'
}

function renderizar(
  aberto: Aberto,
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
    case 'esclarecimento':
      return <CardEsclarecimento key={chave} proposta={aberto.proposta} />
    default: {
      // Um tipo novo na API sem formulário aqui quebra a compilação.
      const naoTratado: never = aberto
      return naoTratado
    }
  }
}
