import { LanguageProvider } from './i18n'
import { Layout } from './layout/Layout'
import { apiBaseUrl } from './lib/api'
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

function Screen({ route }: { route: Route }) {
  switch (route.name) {
    case 'map':
      return <MapScreen />
    case 'report':
      return <ReportScreen />
    case 'tested':
      return <TestedScreen />
    case 'about':
      return <AboutScreen />
    case 'privacy':
      return <PrivacyScreen />
    case 'licences':
      return <LicencesScreen />
    case 'pin':
      return <PinScreen />
  }
}

// LanguageProvider is the root, above everything else, an error boundary included once there is one, so even an
// error screen can show the screen line (S5-R4). Without an API address, the layout shows MS1's banner and
// disables Report.
function App({ apiUrl = API_URL }: { apiUrl?: string }) {
  const route = useRoute()
  return (
    <LanguageProvider>
      <Layout route={route} apiReady={apiUrl !== ''}>
        <Screen route={route} />
      </Layout>
    </LanguageProvider>
  )
}

export default App
