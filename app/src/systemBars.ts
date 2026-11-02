// The APK's status bar (the top bar with the clock and battery). The header is the brand navy and runs edge to edge under
// it, so the bar's icons must be light whatever theme the phone is in; without this a light-mode phone draws dark icons
// on navy. In Capacitor 8's SystemBars, `SystemBarsStyle.Dark` means light icons on a dark background. The navigation bar
// is left alone: the footer above it is the page surface. On the web the plugin has no bars and rejects, so it is never
// called there, and a failure is ignored: the icons are cosmetic and must never stop the app from starting.
import { Capacitor, SystemBars, SystemBarsStyle, SystemBarType } from '@capacitor/core'

export async function styleStatusBar(): Promise<void> {
  if (!Capacitor.isNativePlatform()) return
  try {
    await SystemBars.setStyle({ style: SystemBarsStyle.Dark, bar: SystemBarType.StatusBar })
  } catch {
    // The bar keeps the phone's own style.
  }
}
