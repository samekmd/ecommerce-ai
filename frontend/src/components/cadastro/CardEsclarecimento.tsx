import { Alerta } from '../comuns/Alerta.tsx'
import type { MotivoEsclarecimento, PedidoEsclarecimento } from '../../middlewares/ops/tipos.ts'

const TITULOS: Record<MotivoEsclarecimento, string> = {
  ambiguo: 'Preciso de mais informações',
  nao_suportado: 'Esse pedido não é suportado',
  fora_do_escopo: 'Isso não é um cadastro',
}

// Sem formulário: o usuário reformula a frase ou abre um cadastro manual.
export function CardEsclarecimento({ proposta }: { proposta: PedidoEsclarecimento }) {
  return (
    <Alerta tipo="info" titulo={TITULOS[proposta.motivo]}>
      <p>{proposta.mensagem}</p>
    </Alerta>
  )
}
