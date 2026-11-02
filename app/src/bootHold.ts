// The APK's cold start (Rene, Nov 2): the loading screen in index.html (#boot, inside #root) stays for 5 seconds, its bar
// filling 20 % a second in five steps (20 % at once, 100 % at 4 s), and only then, at 5 s, does React render the app. The
// website renders at once, as before, with the bar sliding. The hold must never keep the app from starting, so a failed platform check, a screen that is not
// in the page, or a step that throws all render at once.
import { Capacitor } from '@capacitor/core'

const STEPS = 5
const STEP_MS = 1000
const PERCENT_PER_STEP = 100 / STEPS

// Starts the hold on the loading screen and calls `done` 5 seconds later. Returns false, with nothing started, when
// there is no hold to run: on the web, or when anything about the screen is not as expected.
function hold(done: () => void): boolean {
  try {
    if (!Capacitor.isNativePlatform()) return false
    const boot = document.getElementById('boot')
    const bar = boot?.querySelector<HTMLElement>('[role="progressbar"]')
    if (!boot || !bar) return false
    // A determinate bar, its accessible name (aria-labelledby) left as it was. The class and the property are the ones
    // index.html's inline CSS reads.
    const show = (step: number) => {
      const percent = step * PERCENT_PER_STEP
      bar.setAttribute('aria-valuenow', String(percent))
      bar.style.setProperty('--boot-progress', `${percent}%`)
    }
    bar.setAttribute('aria-valuemin', '0')
    bar.setAttribute('aria-valuemax', '100')
    // The first step shows at once (20 %), the fifth at 4 s, and the render comes at 5 s, so the full bar is seen for
    // a second before the app enters.
    show(1)
    boot.classList.add('boot-steps')

    let step = 1
    const timer = setInterval(() => {
      step += 1
      if (step <= STEPS) {
        try {
          // From the second step the steps ease (index.html's .boot-eased); the first showed at once.
          boot.classList.add('boot-eased')
          show(step)
          return
        } catch {
          // The screen is not what it was: finish now rather than hold it any longer.
        }
      }
      clearInterval(timer)
      done()
    }, STEP_MS)
    return true
  } catch {
    return false
  }
}

// Calls `render` once: at once on the web, and after the hold on the APK.
export function renderAfterBoot(render: () => void): void {
  if (!hold(render)) render()
}
