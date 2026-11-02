import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource/atkinson-hyperlegible-next/400.css'
import '@fontsource/atkinson-hyperlegible-next/700.css'
import './index.css'
import App from './App.tsx'
import { renderAfterBoot } from './bootHold'
import { rootErrorOptions } from './lib/rootErrors'
import { applyTheme, storedTheme } from './lib/theme'
import { registerServiceWorker } from './pwa'
import { reportFlowBusy } from './report/ReportFlowProvider'
import { styleStatusBar } from './systemBars'

// The theme chosen on About, before the first paint, so a dark choice never flashes light (C624).
applyTheme(storedTheme())

// The root's error handlers log an error's class only, never what it carries (lib/rootErrors.ts). Making the root leaves
// the loading screen in place; the first render replaces it.
const root = createRoot(document.getElementById('root')!, rootErrorOptions)

// The website renders at once. The APK holds the loading screen for 5 seconds first, its bar filling in five steps, and
// any failure there renders at once (bootHold.ts).
renderAfterBoot(() =>
  root.render(
    <StrictMode>
      <App />
    </StrictMode>,
  ),
)

// The APK's status bar gets light icons for the navy header, on the APK only (systemBars.ts).
void styleStatusBar()

// The installable web app's worker, on the web only, held while the report flow holds a photo or a report id.
void registerServiceWorker(reportFlowBusy)
