// Contratos do ops-agent, espelhando docs/api-ops-agent.md. Mudou a API, muda aqui no mesmo PR.

// Dinheiro e percentual trafegam como string para não perder precisão ("100.00").
export type Decimal = string

// ---- Interpretação ----

export type TipoInterpretacao = 'produto' | 'fornecedor' | 'categoria' | 'cupom' | 'esclarecimento'

export type MotivoEsclarecimento = 'ambiguo' | 'nao_suportado' | 'fora_do_escopo'

// O agente só preenche o que a frase trouxe: qualquer campo pode vir null.
export interface ProdutoProposta {
  nome: string
  preco: Decimal | null
  estoque: number | null
  categoria_id: number | null
  fornecedor_id: number | null
  fornecedor_citado: string | null
  avisos: string[]
}

export interface FornecedorProposta {
  nome: string
  cnpj: string | null
  email_contato: string | null
  telefone: string | null
  cidade: string | null
  estado: string | null
  avisos: string[]
}

export interface CategoriaProposta {
  nome: string
  categoria_pai_id: number | null
  avisos: string[]
}

export interface CupomProposta {
  codigo: string | null
  percentual_desconto: Decimal | null
  // YYYY-MM-DD. O contrato diz que vem hoje por padrão, mas o formulário não deve depender disso.
  validade_inicio: string | null
  validade_fim: string | null
  avisos: string[]
}

export interface PedidoEsclarecimento {
  motivo: MotivoEsclarecimento
  mensagem: string
}

interface BaseInterpretacao {
  // null quando a auditoria falhou: o fluxo segue, só não se envia X-Interpretacao-Id.
  interpretacao_id: string | null
  avisos: string[]
}

export type RespostaInterpretar =
  | (BaseInterpretacao & { tipo: 'produto'; proposta: ProdutoProposta })
  | (BaseInterpretacao & { tipo: 'fornecedor'; proposta: FornecedorProposta })
  | (BaseInterpretacao & { tipo: 'categoria'; proposta: CategoriaProposta })
  | (BaseInterpretacao & { tipo: 'cupom'; proposta: CupomProposta })
  | (BaseInterpretacao & { tipo: 'esclarecimento'; proposta: PedidoEsclarecimento })

// ---- Cadastro ----

export interface OpcoesCadastro {
  // Obrigatória aqui de propósito: o formulário gera uma ao abrir e a mantém nos reenvios.
  idempotencyKey: string
  interpretacaoId: string | null
  signal?: AbortSignal
}

export interface ProdutoCadastro {
  nome: string
  sku: string
  preco: Decimal
  estoque: number
  categoria_id: number
  fornecedor_id: number
  // Aceita o resultado de FileReader.readAsDataURL direto, com o prefixo data:.
  imagem: { conteudo_base64: string }
}

export interface ProdutoCriado {
  id: number
  nome: string
  sku: string
  preco: Decimal
  estoque: number
  categoria_id: number
  fornecedor_id: number
}

export interface SkuSugerido {
  sku: string
}

export interface FornecedorCadastro {
  nome: string
  cnpj: string
  email_contato?: string | null
  telefone?: string | null
  cidade: string
  estado: string
}

// Devolvido já normalizado: CNPJ e telefone só com dígitos, UF em maiúsculas.
export interface FornecedorCriado {
  id: number
  nome: string
  cnpj: string
  email_contato: string | null
  telefone: string | null
  cidade: string
  estado: string
  ativo: boolean
}

export interface FornecedorResumo {
  id: number
  nome: string
  cidade: string
  estado: string
}

export interface CategoriaCadastro {
  nome: string
  categoria_pai_id?: number | null
}

export interface CategoriaCriada {
  id: number
  nome: string
  categoria_pai_id: number | null
}

export interface CategoriaResumo {
  id: number
  caminho: string
  folha: boolean
}

export interface CupomCadastro {
  codigo: string
  percentual_desconto: Decimal
  validade_inicio: string
  validade_fim: string
}

export interface CupomCriado extends CupomCadastro {
  id: number
  ativo: boolean
}

// Reexportado para que componentes exibam erros sem importar a camada http.
export type { ErroApi } from '../http/ErroApi.ts'
