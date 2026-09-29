import axios from 'axios'
import { ErroApi, MENSAGEM_GENERICA, ehObjeto, erroSemResposta, traduzirMensagem } from './ErroApi.ts'

// O /interpretar encadeia várias chamadas ao LLM (5 a 60 s); a função dele passa este timeout.
export const TIMEOUT_INTERPRETAR = 90_000

export const FORMATO_USUARIO = /^[A-Za-z0-9._@-]{1,100}$/

export const clienteOps = axios.create({
  baseURL: `${import.meta.env.VITE_OPS_API_URL ?? '/ops'}/api/v1`,
  timeout: 15_000,
})

// middlewares não importa React: o useUsuario empurra o valor para cá quando ele muda.
let usuarioAtual: string | null = null

export function definirUsuario(usuario: string | null): void {
  usuarioAtual = usuario
}

clienteOps.interceptors.request.use((config) => {
  // Sem usuário válido o header não vai, e o 422 do backend em X-Usuario volta como erro de campo.
  if (usuarioAtual !== null && FORMATO_USUARIO.test(usuarioAtual)) {
    config.headers.set('X-Usuario', usuarioAtual)
  }
  return config
})

clienteOps.interceptors.response.use(
  (resposta) => resposta,
  (erro: unknown) => Promise.reject(normalizarErroOps(erro)),
)

interface ErroCampo {
  campo: string | null
  mensagem: string
}

function ehListaErrosCampo(valor: unknown): valor is ErroCampo[] {
  return (
    Array.isArray(valor) &&
    valor.every(
      (item) =>
        ehObjeto(item) &&
        (typeof item.campo === 'string' || item.campo === null) &&
        typeof item.mensagem === 'string',
    )
  )
}

// O formulário tem um único campo de imagem; o erro do base64 pertence a ele.
const CAMPOS_EQUIVALENTES: Record<string, string> = {
  'imagem.conteudo_base64': 'imagem',
}

export function normalizarErroOps(erro: unknown): ErroApi {
  if (erro instanceof ErroApi) return erro
  if (!axios.isAxiosError(erro)) return new ErroApi(0, MENSAGEM_GENERICA)
  if (!erro.response) return erroSemResposta(erro)

  const { status, data } = erro.response

  // O 413 é barrado antes da validação: o único corpo grande que o frontend envia é a imagem.
  if (status === 413) {
    return new ErroApi(status, null, { imagem: 'A imagem excede o tamanho máximo de 2 MB.' })
  }

  if (ehObjeto(data) && ehListaErrosCampo(data.erros)) {
    const gerais: string[] = []
    const campos: Record<string, string> = {}
    for (const { campo, mensagem } of data.erros) {
      const texto = traduzirMensagem(mensagem)
      if (campo === null) {
        // campo null = erro que envolve mais de um campo (ex.: período do cupom).
        gerais.push(texto)
        continue
      }
      const chave = CAMPOS_EQUIVALENTES[campo] ?? campo
      campos[chave] ??= texto
    }
    return new ErroApi(status, gerais.length > 0 ? gerais.join(' ') : null, campos)
  }

  // O ops garante que {"erro"} é genérico e em português; o 500 ganha texto mais útil.
  if (status !== 500 && ehObjeto(data) && typeof data.erro === 'string') {
    return new ErroApi(status, data.erro)
  }

  if (status === 502 || status === 503) {
    return new ErroApi(status, 'Serviço indisponível no momento. Tente novamente em alguns segundos.')
  }
  return new ErroApi(status, MENSAGEM_GENERICA)
}
