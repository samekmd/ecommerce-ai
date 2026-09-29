import { Chat } from '../components/consulta/Chat.tsx'
import { useConversa } from '../hook/useConversa.ts'

export function ConsultaPage() {
  const { mensagens, carregando, erro, enviar, novaConversa } = useConversa()
  return (
    <>
      <h2>Consultas</h2>
      <Chat
        mensagens={mensagens}
        carregando={carregando}
        erro={erro?.message ?? null}
        aoEnviar={(pergunta) => void enviar(pergunta)}
        aoNovaConversa={novaConversa}
      />
    </>
  )
}
