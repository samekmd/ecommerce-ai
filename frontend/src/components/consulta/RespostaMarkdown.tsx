import Markdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import styles from './RespostaMarkdown.module.css'

// Tabela larga rola dentro do balão em vez de estourar a janela; link abre fora da aplicação.
const COMPONENTES: Components = {
  table: ({ node: _node, ...props }) => (
    <div className={styles.tabela}>
      <table {...props} />
    </div>
  ),
  a: ({ node: _node, ...props }) => <a {...props} target="_blank" rel="noopener noreferrer" />,
  // Imagem vinda do LLM carregaria uma URL externa arbitrária: mostra só o texto alternativo.
  img: ({ alt }) => <span className={styles.imagem}>[imagem{alt ? `: ${alt}` : ''}]</span>,
}

// O markdown vira elementos React: HTML bruto dentro da resposta não é interpretado (sem
// rehype-raw) e o urlTransform padrão descarta links javascript:. Nunca usar dangerouslySetInnerHTML.
export function RespostaMarkdown({ texto }: { texto: string }) {
  return (
    <div className={styles.markdown}>
      <Markdown remarkPlugins={[remarkGfm]} components={COMPONENTES}>
        {texto}
      </Markdown>
    </div>
  )
}
