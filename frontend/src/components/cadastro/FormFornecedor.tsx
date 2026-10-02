import { useState, type FormEvent } from 'react'
import { useCadastro } from '../../hook/useCadastro.ts'
import { Alerta } from '../comuns/Alerta.tsx'
import { Botao } from '../comuns/Botao.tsx'
import { Campo } from '../comuns/Campo.tsx'
import type { FornecedorProposta } from '../../middlewares/ops/tipos.ts'
import { ErrosFormulario } from './ErrosFormulario.tsx'
import { UFS, mascararCnpj, mascararTelefone } from './formatacao.ts'
import { ListaAvisos } from './ListaAvisos.tsx'
import styles from './Formulario.module.css'

const CAMPOS = ['nome', 'cnpj', 'email_contato', 'telefone', 'cidade', 'estado'] as const

interface FormFornecedorProps {
  proposta: FornecedorProposta | null
  interpretacaoId: string | null
  avisos: string[]
}

function ufValida(uf: string | null | undefined): string {
  const maiuscula = uf?.trim().toUpperCase() ?? ''
  return (UFS as readonly string[]).includes(maiuscula) ? maiuscula : ''
}

export function FormFornecedor({ proposta, interpretacaoId, avisos }: FormFornecedorProps) {
  const [nome, setNome] = useState(proposta?.nome ?? '')
  const [cnpj, setCnpj] = useState(mascararCnpj(proposta?.cnpj ?? ''))
  const [email, setEmail] = useState(proposta?.email_contato ?? '')
  const [telefone, setTelefone] = useState(mascararTelefone(proposta?.telefone ?? ''))
  const [cidade, setCidade] = useState(proposta?.cidade ?? '')
  const [estado, setEstado] = useState(ufValida(proposta?.estado))
  const [errosLocais, setErrosLocais] = useState<Record<string, string>>({})

  const { dados: criado, carregando, erro, executar } = useCadastro('fornecedor', interpretacaoId)
  const erroDe = (campo: string) => errosLocais[campo] ?? erro?.campos[campo] ?? null

  async function enviar(evento: FormEvent) {
    evento.preventDefault()
    const erros: Record<string, string> = {}
    if (!nome.trim()) erros.nome = 'Informe o nome.'
    // Os dígitos verificadores são conferidos pelo backend; aqui só o tamanho.
    if (cnpj.replace(/\D/g, '').length !== 14) erros.cnpj = 'Informe os 14 dígitos do CNPJ.'
    if (!cidade.trim()) erros.cidade = 'Informe a cidade.'
    if (!estado) erros.estado = 'Escolha a UF.'
    setErrosLocais(erros)
    if (Object.keys(erros).length > 0) return

    // Enviado como digitado (com máscara): o backend normaliza.
    const resultado = await executar({
      nome: nome.trim(),
      cnpj,
      email_contato: email.trim() || null,
      telefone: telefone.trim() || null,
      cidade: cidade.trim(),
      estado,
    })
    if (resultado) {
      setNome('')
      setCnpj('')
      setEmail('')
      setTelefone('')
      setCidade('')
      setEstado('')
    }
  }

  return (
    <form onSubmit={enviar} noValidate className={styles.formulario} aria-labelledby="titulo-fornecedor">
      <h3 id="titulo-fornecedor" className={styles.titulo}>
        Cadastro de fornecedor
      </h3>
      {!criado && <ListaAvisos avisos={avisos} />}
      {criado && (
        <Alerta tipo="sucesso" titulo="Fornecedor cadastrado">
          <ul className={styles.criado}>
            <li>ID: {criado.id}</li>
            <li>
              {criado.nome} — {criado.cidade}/{criado.estado}
            </li>
          </ul>
        </Alerta>
      )}
      <ErrosFormulario erro={erro} camposExibidos={CAMPOS} />

      <Campo rotulo="Nome" obrigatorio erro={erroDe('nome')}>
        {(c) => <input {...c} value={nome} onChange={(e) => setNome(e.target.value)} />}
      </Campo>
      <Campo rotulo="CNPJ" obrigatorio erro={erroDe('cnpj')}>
        {(c) => (
          <input
            {...c}
            inputMode="numeric"
            value={cnpj}
            onChange={(e) => setCnpj(mascararCnpj(e.target.value))}
            placeholder="00.000.000/0000-00"
          />
        )}
      </Campo>
      <div className={styles.linha}>
        <Campo rotulo="E-mail de contato" erro={erroDe('email_contato')}>
          {(c) => <input {...c} type="email" value={email} onChange={(e) => setEmail(e.target.value)} />}
        </Campo>
        <Campo rotulo="Telefone" erro={erroDe('telefone')}>
          {(c) => (
            <input
              {...c}
              type="tel"
              value={telefone}
              onChange={(e) => setTelefone(mascararTelefone(e.target.value))}
              placeholder="(00) 00000-0000"
            />
          )}
        </Campo>
      </div>
      <div className={styles.linha}>
        <Campo rotulo="Cidade" obrigatorio erro={erroDe('cidade')}>
          {(c) => <input {...c} value={cidade} onChange={(e) => setCidade(e.target.value)} />}
        </Campo>
        <Campo rotulo="UF" obrigatorio erro={erroDe('estado')}>
          {(c) => (
            <select {...c} value={estado} onChange={(e) => setEstado(e.target.value)}>
              <option value="">Escolha</option>
              {UFS.map((uf) => (
                <option key={uf} value={uf}>
                  {uf}
                </option>
              ))}
            </select>
          )}
        </Campo>
      </div>

      <div className={styles.acoes}>
        <Botao type="submit" carregando={carregando}>
          {carregando ? 'Cadastrando…' : 'Confirmar cadastro'}
        </Botao>
      </div>
    </form>
  )
}
