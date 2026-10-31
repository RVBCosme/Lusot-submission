import { useEffect, useState } from 'react'
import { T } from '../i18n'

// Offline, the app says so (C621): the map, reports and samples need the network. It shows while the browser says it
// is offline, and goes when it is back.
export function OfflineBanner() {
  const [offline, setOffline] = useState(() => navigator.onLine === false)
  useEffect(() => {
    const on = () => setOffline(false)
    const off = () => setOffline(true)
    window.addEventListener('online', on)
    window.addEventListener('offline', off)
    return () => {
      window.removeEventListener('online', on)
      window.removeEventListener('offline', off)
    }
  }, [])
  if (!offline) return null
  return (
    <p role="status" className="mt-2 rounded-control border border-outline p-2">
      <T k="layout.offline" />
    </p>
  )
}
