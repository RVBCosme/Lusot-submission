import { referenceLine } from '../copy/wording'
import { Line, T, useLanguage, useT } from '../i18n'
import { formatDateTime } from '../lib/time'

// What a reading's references and a reason are made of, as GET /reports/{id} gives them (MS4's C507).
export type DetailReference = { id: number; dropped: string | null; landmark: string | null }

// A reason code is a short code such as `too_dark`. A value that isn't one is left out, so no error text, address or id
// the API might send ever reaches the screen (C610).
const REASON_CODE = /^[a-z0-9_]{1,64}$/

// The "Details" disclosure (spec §4.2): the reason code, the photo's time, and each reference object with where the
// water meets it, or why it wasn't used. A dropped reference shows its cause and no level, since its level is null
// (amendments 2 and 2a). Never a report id, a URL or an error message (C610). With nothing to show, nothing is drawn.
export function Details({
  reasonCode,
  photoTime,
  references = [],
}: {
  reasonCode?: string
  photoTime?: string
  references?: readonly DetailReference[]
}) {
  const t = useT()
  const { lang } = useLanguage()
  const code = reasonCode !== undefined && REASON_CODE.test(reasonCode) ? reasonCode : undefined
  const time = photoTime === undefined ? undefined : formatDateTime(lang, photoTime)
  const items = references.flatMap((reference) => {
    const line = referenceLine(t, reference)
    return line === undefined ? [] : [{ id: reference.id, line }]
  })
  if (code === undefined && time === undefined && items.length === 0) return null
  return (
    <details className="mt-4">
      <summary className="flex min-h-tap cursor-pointer items-center text-action underline underline-offset-4">
        <T k="result.details" />
      </summary>
      <div className="pb-2 text-small text-ink-2">
        {code !== undefined && (
          <p>
            <Line value={t('result.details.reason', { code })} />
          </p>
        )}
        {time !== undefined && (
          <p className="mt-1">
            <Line value={t('result.details.photoTime', { time })} />
          </p>
        )}
        {items.length > 0 && (
          <>
            <p className="mt-3 font-bold text-ink">
              <T k="result.details.references" />
            </p>
            <ul className="mt-1">
              {items.map(({ id, line }) => (
                <li key={id} className="mt-1">
                  <span className="font-bold">
                    <Line value={t('result.reference', { id })} />
                  </span>{' '}
                  <Line value={line} />
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </details>
  )
}
