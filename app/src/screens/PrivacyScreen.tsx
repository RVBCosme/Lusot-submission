import { Markdown } from '../components/Markdown'
import { DEMO } from '../demo'
import privacyText from '../content/privacy.en.md?raw'
import { T } from '../i18n'
import { EN } from '../i18n/en'

// Window 4's privacy policy (C605): its title and "Not affiliated with MMDA." from the string table, its sections
// from privacy.en.md, and the screen line from the layout. Taglish shows the English text until Rene approves its
// Taglish (C619). The contact comes from VITE_PRIVACY_CONTACT, set in the git-ignored app/.env.local at build
// time, never from the repo (PRIV-Q4); until then the page says when it will be added, in the policy's English.
export function PrivacyScreen() {
  const contact = import.meta.env.VITE_PRIVACY_CONTACT?.trim() || EN['privacy.contactPending'].text
  return (
    <article className="max-w-prose">
      <h1 className="text-title font-bold">
        <T k="privacy.title" />
      </h1>
      <p className="mt-2 text-small text-ink-2">
        <T k="about.notAffiliated" />
      </p>
      {DEMO && (
        <p className="mt-4 rounded-control border border-outline p-2">
          <T k="demo.privacy" />
        </p>
      )}
      <Markdown source={privacyText} lang="en" vars={{ privacyContact: contact }} className="mt-4" testId="policy" />
    </article>
  )
}
