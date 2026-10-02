import { CaixaFrase } from '../components/cadastro/CaixaFrase.tsx'
import { CardEsclarecimento } from '../components/cadastro/CardEsclarecimento.tsx'
import { IdentificacaoUsuario } from '../components/cadastro/IdentificacaoUsuario.tsx'
import { ModalAguardandoAgente } from '../components/cadastro/ModalAguardandoAgente.tsx'
import { useInterpretar } from '../hook/useInterpretar.ts'
import { usePropostaAgente } from '../hook/usePropostaAgente.ts'
import { useUsuario } from '../hook/useUsuario.ts'
import { FormularioCadastroPage } from './FormularioCadastroPage.tsx'

export function CadastroPage() {
  const { usuario } = useUsuario()
  const proposta = usePropostaAgente()

  // Sem roteador: com uma proposta guardada, a aba mostra a página do formulário no lugar da iteração.
  if (usuario && proposta.aberto) {
    return <FormularioCadastroPage aberto={proposta.aberto} aoVoltar={proposta.descartar} aoAbrir={proposta.abrir} />
  }

  return (
    <>
      <h2>Cadastro</h2>
      <IdentificacaoUsuario />
      {/* Sem usuário o backend recusa o cadastro (X-Usuario é obrigatório). */}
      {usuario && <IteracaoAgente proposta={proposta} />}
    </>
  )
}

function IteracaoAgente({ proposta }: { proposta: ReturnType<typeof usePropostaAgente> }) {
  const interpretacao = useInterpretar()

  async function interpretar(mensagem: string) {
    const resposta = await interpretacao.executar(mensagem)
    if (resposta) proposta.receber(resposta, mensagem)
  }

  return (
    <>
      <CaixaFrase
        fraseInicial={proposta.ultimaFrase}
        aoInterpretar={(m) => void interpretar(m)}
        carregando={interpretacao.carregando}
        erro={interpretacao.erro?.message ?? null}
      />
      {proposta.esclarecimento && <CardEsclarecimento proposta={proposta.esclarecimento} />}
      <ModalAguardandoAgente aberto={interpretacao.carregando} aoCancelar={interpretacao.cancelar} />
    </>
  )
}
