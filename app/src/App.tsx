import { AskScreen } from './ask/AskScreen'
import { LanguageProvider } from './i18n'
import { Layout } from './layout/Layout'
import { apiBaseUrl } from './lib/api'
import { GateProvider, NoticeGate } from './lib/consent'
import { ReportFlowProvider } from './report/ReportFlowProvider'
import { useRoute, type Route } from './router'
import { AboutScreen } from './screens/AboutScreen'
import { LicencesScreen } from './screens/LicencesScreen'
import { MapScreen } from './screens/MapScreen'
import { PinScreen } from './screens/PinScreen'
import { PrivacyScreen } from './screens/PrivacyScreen'
import { ReportScreen } from './screens/ReportScreen'
import { TestedScreen } from './screens/TestedScreen'

// Read once at load (MS1's R31). Tests pass their own apiUrl.
const API_URL = apiBaseUrl(import.meta.env.VITE_API_URL)

function Screen({ route, apiUrl }: { route: Route; apiUrl: string }) {
  switch (route.name) {
    case 'map':
      return <MapScreen apiUrl={apiUrl} />
    case 'report':
      // The notice guards the screen itself, so a typed #/report meets it before the camera opens (C605).
      return (
        <NoticeGate>
          <ReportScreen apiUrl={apiUrl} />
        </NoticeGate>
      )
    case 'tested':
      return <TestedScreen apiUrl={apiUrl} />
    case 'about':
      return <AboutScreen />
    case 'privacy':
      return <PrivacyScreen />
    case 'licences':
      return <LicencesScreen />
    case 'ask':
      return <AskScreen apiUrl={apiUrl} />
    case 'pin':
      // The pin screen asks the API for a pin's report only for an id that `GET /map/pins` holds (S5-R5).
      return <PinScreen apiUrl={apiUrl} id={route.id} />
  }
}

// LanguageProvider is the root, above everything else, the layout's error boundary included, so even an error
// screen can show the screen line (S5-R4). Without an API address, the layout shows MS1's banner and
// disables Report, and a typed #/report refuses. The report flow sits above the routes, so a wait goes on while
// the person looks at the map, and its result is there when they come back. GateProvider sits inside the layout's
// <main>, so an open gate stays under the screen-line bar, and the route's fresh <main> drops a gate left open on
// the screen before.
function App({ apiUrl = API_URL }: { apiUrl?: string }) {
  const route = useRoute()
  return (
    <LanguageProvider>
      <ReportFlowProvider apiUrl={apiUrl}>
        <Layout route={route} apiReady={apiUrl !== ''}>
          <GateProvider>
            <Screen route={route} apiUrl={apiUrl} />
          </GateProvider>
        </Layout>
      </ReportFlowProvider>
    </LanguageProvider>
  )
}

export default App
