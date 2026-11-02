import { useEffect, useId, useRef, useState } from 'react'
import { T, useT } from '../i18n'
import { useHeadingFocus } from '../lib/focus'

// The licence texts of everything the web app and the APK ship (C636). `npm run build -w app` writes them to
// app/public/licences.txt (scripts/licences.mjs), and the page reads that file from its own origin with a plain
// fetch: no API call, so it works wherever the page itself loads. The text stays English, as its authors wrote it.
const LICENCES_URL = './licences.txt'
const OSM_COPYRIGHT = 'https://www.openstreetmap.org/copyright'
const LINK = 'inline-flex min-h-tap min-w-tap items-center text-action underline underline-offset-4'

type State = { kind: 'loading' } | { kind: 'ready'; text: string } | { kind: 'failed' }

export function LicencesScreen() {
  const t = useT()
  const [state, setState] = useState<State>({ kind: 'loading' })
  const heading = useRef<HTMLHeadingElement>(null)
  const otherTitle = useId()
  const packagesTitle = useId()
  useHeadingFocus(heading, undefined)

  useEffect(() => {
    const abort = new AbortController()
    fetch(LICENCES_URL, { signal: abort.signal })
      .then(async (response) => {
        // A dev server answers an unknown file with the app's own page, so a page counts as no file.
        const isPage = response.headers.get('content-type')?.includes('text/html') === true
        const text = response.ok && !isPage ? await response.text() : ''
        if (abort.signal.aborted) return
        setState(text.trim() === '' ? { kind: 'failed' } : { kind: 'ready', text })
      })
      .catch(() => {
        if (!abort.signal.aborted) setState({ kind: 'failed' })
      })
    return () => abort.abort()
  }, [])

  return (
    <article className="max-w-prose">
      <h1 ref={heading} className="text-title font-bold">
        <T k="licences.title" />
      </h1>
      <p className="mt-3">
        <T k="licences.intro" />
      </p>

      <section aria-labelledby={otherTitle} className="mt-6">
        <h2 id={otherTitle} className="text-heading font-bold">
          <T k="licences.otherTitle" />
        </h2>
        <p className="mt-2">
          <T k="licences.osm" />
        </p>
        <p>
          <a href={OSM_COPYRIGHT} target="_blank" rel="noopener" className={LINK}>
            <T k="licences.osmLink" />
          </a>
        </p>
        <p className="mt-2">
          <T k="licences.samples" />
        </p>
        <p className="mt-2">
          <T k="licences.brand" />
        </p>
      </section>

      <section aria-labelledby={packagesTitle} className="mt-6">
        <h2 id={packagesTitle} className="text-heading font-bold">
          <T k="licences.packagesTitle" />
        </h2>
        <p className="mt-2">
          <T k="licences.packagesNote" />
        </p>
        {state.kind === 'ready' ? (
          // A scrolling box the keyboard can reach, so the long text never pushes the rest of the screen away.
          <div
            role="region"
            aria-label={t('licences.textLabel').text}
            tabIndex={0}
            className="mt-4 max-h-[60dvh] overflow-auto rounded-control border border-outline p-3"
          >
            <pre lang="en" className="font-sans text-small break-words whitespace-pre-wrap">
              {state.text}
            </pre>
          </div>
        ) : (
          <p role="status" className="mt-4 text-ink-2">
            <T k={state.kind === 'loading' ? 'licences.loading' : 'licences.unavailable'} />
          </p>
        )}
      </section>
    </article>
  )
}
