import { useState } from 'react'
import styles from './App.module.css'
import { CadastroPage } from './pages/CadastroPage.tsx'
import { ConsultaPage } from './pages/ConsultaPage.tsx'

type Aba = 'cadastro' | 'consulta'

const ABAS: { id: Aba; rotulo: string }[] = [
  { id: 'cadastro', rotulo: 'Cadastro' },
  { id: 'consulta', rotulo: 'Consultas' },
]

function App() {
  const [aba, setAba] = useState<Aba>('cadastro')

  return (
    <main className={styles.app}>
      <div role="tablist" aria-label="Seções" className={styles.abas}>
        {ABAS.map(({ id, rotulo }) => (
          <button
            key={id}
            type="button"
            role="tab"
            id={`aba-${id}`}
            aria-selected={aba === id}
            aria-controls={`painel-${id}`}
            className={styles.aba}
            onClick={() => setAba(id)}
          >
            {rotulo}
          </button>
        ))}
      </div>
      <div role="tabpanel" id={`painel-${aba}`} aria-labelledby={`aba-${aba}`}>
        {aba === 'cadastro' ? <CadastroPage /> : <ConsultaPage />}
      </div>
    </main>
  )
}

export default App
