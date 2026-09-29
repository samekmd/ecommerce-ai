import axios from 'axios'
import { ErroApi, MENSAGEM_GENERICA, ehObjeto, erroSemResposta, traduzirMensagem } from './ErroApi.ts'

// O agente faz até 10 iterações com o LLM (60 s cada no teto) e SQL de até 20 s.
export const clienteQuery = axios.create({
  baseURL: import.meta.env.VITE_QUERY_API_URL ?? '/query',
  timeout: 120_000,
})

clienteQuery.interceptors.response.use(
  (resposta) => resposta,
  (erro: unknown) => Promise.reject(normalizarErroQuery(erro)),
)

interface ErroValidacaoItem {
  loc: (string | number)[]
  msg: string
}

function ehListaErrosValidacao(valor: unknown): valor is ErroValidacaoItem[] {
  return (
    Array.isArray(valor) &&
    valor.every(
      (item) =>
        ehObjeto(item) &&
        Array.isArray(item.loc) &&
        item.loc.every((parte) => typeof parte === 'string' || typeof parte === 'number') &&
        typeof item.msg === 'string',
    )
  )
}

// O detail de 5xx traz o texto da exceção interna: nunca é lido, só o status importa.
const MENSAGENS_POR_STATUS: Record<number, string> = {
  502: 'O agente não conseguiu responder agora. Tente novamente em alguns segundos.',
  503: 'O banco da loja está indisponível no momento. Tente novamente.',
}

export function normalizarErroQuery(erro: unknown): ErroApi {
  if (erro instanceof ErroApi) return erro
  if (!axios.isAxiosError(erro)) return new ErroApi(0, MENSAGEM_GENERICA)
  if (!erro.response) return erroSemResposta(erro)

  const { status, data } = erro.response

  if (status === 422 && ehObjeto(data) && ehListaErrosValidacao(data.detail)) {
    // O item ecoa o valor enviado em `input`; ele é descartado aqui e nunca sai desta função.
    const gerais: string[] = []
    const campos: Record<string, string> = {}
    for (const { loc, msg } of data.detail) {
      const texto = traduzirMensagem(msg)
      // Sem nome de campo no fim do loc o problema é o corpo inteiro: ["body"] ou, no JSON
      // malformado, ["body", <posição do caractere>].
      const campo = loc.length >= 2 ? loc[loc.length - 1] : undefined
      if (typeof campo !== 'string') {
        gerais.push(texto)
        continue
      }
      campos[campo] ??= texto
    }
    return new ErroApi(status, gerais.length > 0 ? gerais.join(' ') : null, campos)
  }

  return new ErroApi(status, MENSAGENS_POR_STATUS[status] ?? MENSAGEM_GENERICA)
}
