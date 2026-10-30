import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource/atkinson-hyperlegible-next/400.css'
import '@fontsource/atkinson-hyperlegible-next/700.css'
import './index.css'
import App from './App.tsx'
import { applyTheme, storedTheme } from './lib/theme'

// The theme chosen on About, before the first paint, so a dark choice never flashes light (C624).
applyTheme(storedTheme())

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
