import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource/atkinson-hyperlegible-next/400.css'
import '@fontsource/atkinson-hyperlegible-next/700.css'
import './index.css'
import App from './App.tsx'
import { rootErrorOptions } from './lib/rootErrors'
import { applyTheme, storedTheme } from './lib/theme'
import { registerServiceWorker } from './pwa'
import { reportFlowBusy } from './report/ReportFlowProvider'

// The theme chosen on About, before the first paint, so a dark choice never flashes light (C624).
applyTheme(storedTheme())

// The root's error handlers log an error's class only, never what it carries (lib/rootErrors.ts).
createRoot(document.getElementById('root')!, rootErrorOptions).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

// The installable web app's worker, on the web only, held while the report flow holds a photo or a report id.
void registerServiceWorker(reportFlowBusy)
