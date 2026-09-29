// Funções puras de entrada e exibição usadas pelos formulários de cadastro.

// Aceita "100", "99,9", "1.234,56" e devolve "100.00", "99.90", "1234.56" sem passar por
// number (que perderia precisão). null = texto que não é um valor com até 2 casas.
export function normalizarDecimal(texto: string): string | null {
  let valor = texto.replace(/\s/g, '')
  // Com vírgula, ela é o separador decimal e os pontos são de milhar.
  if (valor.includes(',')) valor = valor.replace(/\./g, '').replace(',', '.')
  if (!/^\d+(\.\d{1,2})?$/.test(valor)) return null
  const [inteira, fracao = ''] = valor.split('.')
  return `${inteira.replace(/^0+(?=\d)/, '')}.${fracao.padEnd(2, '0')}`
}

export function ehZero(decimal: string): boolean {
  return /^0+\.0+$/.test(decimal)
}

export function formatarMoeda(decimal: string): string {
  // Number só para exibir; o valor enviado continua sendo a string.
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(Number(decimal))
}

function digitos(texto: string, maximo: number): string {
  return texto.replace(/\D/g, '').slice(0, maximo)
}

// Máscaras só na tela: o backend aceita com ou sem máscara e normaliza.
export function mascararCnpj(texto: string): string {
  const d = digitos(texto, 14)
  return d
    .replace(/^(\d{2})(\d)/, '$1.$2')
    .replace(/^(\d{2})\.(\d{3})(\d)/, '$1.$2.$3')
    .replace(/\.(\d{3})(\d)/, '.$1/$2')
    .replace(/(\d{4})(\d)/, '$1-$2')
}

export function mascararTelefone(texto: string): string {
  const d = digitos(texto, 11)
  if (d.length <= 2) return d.length ? `(${d}` : ''
  const ddd = d.slice(0, 2)
  const numero = d.slice(2)
  // 8 dígitos (fixo) quebram em 4-4; 9 dígitos (celular) em 5-4.
  const corte = numero.length > 8 ? 5 : 4
  return numero.length > corte
    ? `(${ddd}) ${numero.slice(0, corte)}-${numero.slice(corte)}`
    : `(${ddd}) ${numero}`
}

export const UFS = [
  'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS', 'MG', 'PA',
  'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO',
] as const

// "Hoje" no fuso da loja, já como YYYY-MM-DD. Criar um Date a partir de uma data sem hora
// deslocaria o dia pelo fuso; aqui o Date é só o instante atual.
export function hojeSaoPaulo(): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Sao_Paulo' }).format(new Date())
}
