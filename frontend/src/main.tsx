import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './assets/tema.css'
import './assets/global.css'
import App from './App.tsx'
import { UsuarioProvider } from './hook/UsuarioProvider.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <UsuarioProvider>
      <App />
    </UsuarioProvider>
  </StrictMode>,
)
