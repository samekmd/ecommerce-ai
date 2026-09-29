import { useState, type FormEvent } from 'react'
import { useCadastro } from '../../hook/useCadastro.ts'
import { useSkuSugerido } from '../../hook/useSkuSugerido.ts'
import { Alerta } from '../comuns/Alerta.tsx'
import { Botao } from '../comuns/Botao.tsx'
import { Campo } from '../comuns/Campo.tsx'
import { SeletorImagem } from '../comuns/SeletorImagem.tsx'
import type { CategoriaResumo, ProdutoProposta } from '../../middlewares/ops/tipos.ts'
import { AutocompleteFornecedor, type FornecedorEscolhido } from './AutocompleteFornecedor.tsx'
import { ErrosFormulario } from './ErrosFormulario.tsx'
import { ehZero, formatarMoeda, normalizarDecimal } from './formatacao.ts'
import { ListaAvisos } from './ListaAvisos.tsx'
import { SelectCategoria } from './SelectCategoria.tsx'
import styles from './Formulario.module.css'

const CAMPOS = ['nome', 'sku', 'preco', 'estoque', 'categoria_id', 'fornecedor_id', 'imagem'] as const

interface FormProdutoProps {
  proposta: ProdutoProposta | null
  interpretacaoId: string | null
  avisos: string[]
  categorias: CategoriaResumo[] | null
  aoCadastrarFornecedor: (nome: string) => void
}

export function FormProduto({ proposta, interpretacaoId, avisos, categorias, aoCadastrarFornecedor }: FormProdutoProps) {
  const [nome, setNome] = useState(proposta?.nome ?? '')
  const [preco, setPreco] = useState(proposta?.preco?.replace('.', ',') ?? '')
  const [estoque, setEstoque] = useState(proposta?.estoque?.toString() ?? '')
  const [categoriaId, setCategoriaId] = useState<number | null>(proposta?.categoria_id ?? null)
  const [fornecedor, setFornecedor] = useState<FornecedorEscolhido | null>(
    proposta?.fornecedor_id != null
      ? { id: proposta.fornecedor_id, nome: proposta.fornecedor_citado ?? `Fornecedor #${proposta.fornecedor_id}` }
      : null,
  )
  const [imagem, setImagem] = useState<string | null>(null)
  const [errosLocais, setErrosLocais] = useState<Record<string, string>>({})
  // Remonta o autocomplete ao limpar o formulário, zerando o termo de busca.
  const [versao, setVersao] = useState(0)

  const sku = useSkuSugerido(categoriaId)
  const { dados: criado, carregando, erro, executar } = useCadastro('produto', interpretacaoId)
  const erroDe = (campo: string) => errosLocais[campo] ?? erro?.campos[campo] ?? null

  async function enviar(evento: FormEvent) {
    evento.preventDefault()
    const erros: Record<string, string> = {}
    const precoNormalizado = normalizarDecimal(preco)
    if (!nome.trim()) erros.nome = 'Informe o nome.'
    if (!sku.sku.trim()) erros.sku = 'Informe o SKU.'
    if (!preco.trim()) erros.preco = 'Informe o preço.'
    else if (precoNormalizado === null) erros.preco = 'Use um valor como 99,90.'
    else if (ehZero(precoNormalizado)) erros.preco = 'O preço deve ser maior que zero.'
    if (!/^\d+$/.test(estoque.trim())) erros.estoque = 'Informe um número inteiro, 0 ou mais.'
    if (categoriaId === null) erros.categoria_id = 'Escolha a categoria.'
    if (fornecedor === null) erros.fornecedor_id = 'Escolha o fornecedor.'
    if (imagem === null) erros.imagem = 'Anexe uma imagem do produto.'
    setErrosLocais(erros)
    if (Object.keys(erros).length > 0 || precoNormalizado === null || categoriaId === null || fornecedor === null || imagem === null) {
      return
    }

    const resultado = await executar({
      nome: nome.trim(),
      sku: sku.sku.trim(),
      preco: precoNormalizado,
      estoque: Number.parseInt(estoque, 10),
      categoria_id: categoriaId,
      fornecedor_id: fornecedor.id,
      imagem: { conteudo_base64: imagem },
    })
    if (resultado) {
      setNome('')
      setPreco('')
      setEstoque('')
      setCategoriaId(null)
      setFornecedor(null)
      setImagem(null)
      setVersao((v) => v + 1)
      sku.reiniciar()
    }
  }

  return (
    <form onSubmit={enviar} noValidate className={styles.formulario} aria-labelledby="titulo-produto">
      <h3 id="titulo-produto" className={styles.titulo}>
        Cadastro de produto
      </h3>
      {!criado && <ListaAvisos avisos={avisos} />}
      {criado && (
        <Alerta tipo="sucesso" titulo="Produto cadastrado">
          <ul className={styles.criado}>
            <li>ID: {criado.id}</li>
            <li>SKU: {criado.sku}</li>
            <li>
              {criado.nome} — {formatarMoeda(criado.preco)}, estoque {criado.estoque}
            </li>
          </ul>
        </Alerta>
      )}
      <ErrosFormulario erro={erro} camposExibidos={CAMPOS} />

      <Campo rotulo="Nome" obrigatorio erro={erroDe('nome')}>
        {(c) => <input {...c} value={nome} onChange={(e) => setNome(e.target.value)} />}
      </Campo>
      <div className={styles.linha}>
        <Campo rotulo="Preço (R$)" obrigatorio erro={erroDe('preco')}>
          {(c) => <input {...c} inputMode="decimal" value={preco} onChange={(e) => setPreco(e.target.value)} placeholder="0,00" />}
        </Campo>
        <Campo rotulo="Estoque" obrigatorio erro={erroDe('estoque')}>
          {(c) => <input {...c} type="number" min={0} step={1} value={estoque} onChange={(e) => setEstoque(e.target.value)} />}
        </Campo>
      </div>
      <Campo rotulo="Categoria" obrigatorio erro={erroDe('categoria_id')}>
        {(c) => (
          <SelectCategoria
            controle={c}
            categorias={categorias}
            valor={categoriaId}
            aoAlterar={setCategoriaId}
            rotuloVazio="Escolha a categoria"
            destacarFolhas
          />
        )}
      </Campo>
      <Campo
        rotulo="SKU"
        obrigatorio
        dica={sku.carregando ? 'Buscando sugestão…' : 'Sugestão pela categoria; pode editar. Não fica reservado.'}
        erro={erroDe('sku') ?? sku.erro?.message ?? null}
      >
        {(c) => <input {...c} value={sku.sku} onChange={(e) => sku.alterarSku(e.target.value)} />}
      </Campo>
      <Campo rotulo="Fornecedor" obrigatorio erro={erroDe('fornecedor_id')}>
        {(c) => (
          <AutocompleteFornecedor
            key={versao}
            controle={c}
            selecionado={fornecedor}
            aoSelecionar={setFornecedor}
            termoInicial={proposta?.fornecedor_citado ?? ''}
            aoCadastrarNovo={aoCadastrarFornecedor}
          />
        )}
      </Campo>
      <SeletorImagem key={versao} rotulo="Imagem" obrigatorio valor={imagem} aoAlterar={setImagem} erro={erroDe('imagem')} />

      <div className={styles.acoes}>
        <Botao type="submit" carregando={carregando}>
          {carregando ? 'Cadastrando…' : 'Confirmar cadastro'}
        </Botao>
      </div>
    </form>
  )
}
