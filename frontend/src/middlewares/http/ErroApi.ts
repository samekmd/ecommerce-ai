import type { AxiosError } from 'axios'

// Formato único de erro das duas APIs. Hooks e componentes só conhecem esta classe:
// quem monta uma ErroApi é o interceptor de cada cliente (clienteOps, clienteQuery).
export class ErroApi extends Error {
  // 0 = a requisição não chegou a ter resposta (rede, timeout ou cancelamento).
  readonly status: number
  readonly geral: string | null
  readonly campos: Record<string, string>

  constructor(status: number, geral: string | null, campos: Record<string, string> = {}) {
    super(geral ?? Object.values(campos)[0] ?? MENSAGEM_GENERICA)
    this.name = 'ErroApi'
    this.status = status
    this.geral = geral
    this.campos = campos
  }
}

export const MENSAGEM_GENERICA = 'Erro inesperado. Tente novamente.'

// O backend usa Pydantic; as mensagens de formato chegam em inglês e são padronizadas.
const TRADUCOES: [RegExp, (m: RegExpMatchArray) => string][] = [
  [/^Field required/, () => 'Campo obrigatório.'],
  [/^String should have at least (\d+) characters?/, (m) =>
    `Deve ter pelo menos ${m[1]} ${m[1] === '1' ? 'caractere' : 'caracteres'}.`],
  [/^String should have at most (\d+) characters?/, (m) =>
    `Deve ter no máximo ${m[1]} ${m[1] === '1' ? 'caractere' : 'caracteres'}.`],
  [/^String should match pattern/, () => 'Formato inválido.'],
  [/^Input should be greater than or equal to (\S+)/, (m) => `Deve ser maior ou igual a ${m[1]}.`],
  [/^Input should be greater than (\S+)/, (m) => `Deve ser maior que ${m[1]}.`],
  [/^Input should be less than or equal to (\S+)/, (m) => `Deve ser menor ou igual a ${m[1]}.`],
  [/^Input should be less than (\S+)/, (m) => `Deve ser menor que ${m[1]}.`],
  [/^Input should be a valid integer/, () => 'Deve ser um número inteiro.'],
  [/^Input should be a valid (number|decimal)/, () => 'Deve ser um número.'],
  [/^Decimal input should have no more than (\d+) decimal places?/, (m) =>
    `Deve ter no máximo ${m[1]} ${m[1] === '1' ? 'casa decimal' : 'casas decimais'}.`],
  [/^Decimal input should have no more than (\d+) digits?/, () => 'Número grande demais.'],
  [/^Input should be a valid string/, () => 'Deve ser um texto.'],
  [/^Input should be a valid date/, () => 'Data inválida.'],
  [/^value is not a valid email address/, () => 'E-mail inválido.'],
  [/^Extra inputs are not permitted/, () => 'Campo não permitido.'],
  [/^JSON decode error/, () => 'Requisição inválida.'],
]

// Mensagem do Pydantic sem tradução conhecida: melhor genérica em português que inglês na tela.
const PARECE_PYDANTIC = /^(Input|String|Value|Field|Decimal|List|Extra|JSON|value is)\b/

export function traduzirMensagem(mensagem: string): string {
  const texto = mensagem.replace(/^Value error, /, '')
  for (const [padrao, traduzir] of TRADUCOES) {
    const encontrado = texto.match(padrao)
    if (encontrado) return traduzir(encontrado)
  }
  // As mensagens de regra de negócio do ops já vêm em português e passam como estão.
  return PARECE_PYDANTIC.test(texto) ? 'Valor inválido.' : texto
}

export function erroSemResposta(erro: AxiosError): ErroApi {
  if (erro.code === 'ERR_CANCELED') return new ErroApi(0, 'Requisição cancelada.')
  if (erro.code === 'ECONNABORTED' || erro.code === 'ETIMEDOUT') {
    return new ErroApi(0, 'O servidor demorou demais para responder. Tente novamente.')
  }
  return new ErroApi(0, 'Não foi possível conectar ao servidor. Verifique sua conexão.')
}

export function ehObjeto(valor: unknown): valor is Record<string, unknown> {
  return typeof valor === 'object' && valor !== null
}
