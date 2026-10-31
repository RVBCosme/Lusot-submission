/// <reference types="vite-plugin-pwa/client" />

interface ImportMetaEnv {
  // The HTTP API's base URL, from .env.local. It is missing from a build made without that file.
  readonly VITE_API_URL: string | undefined
  // '1' for a release build: the copy-review check then fails while any string is unreviewed (C609).
  readonly VITE_LUSOT_RELEASE: string | undefined
  // '1' in a development build to answer every API call from app/src/mock/ instead (C628). Ignored in a production build.
  readonly VITE_API_MOCK: string | undefined
  // The mock's scenario, one of those app/src/mock/fixtures.ts lists; `?mock=<scenario>` on the page's URL wins.
  readonly VITE_API_MOCK_SCENARIO: string | undefined
  // The privacy policy's contact (PRIV-Q4), from the git-ignored .env.local only, never a committed file. Unset or
  // blank, the policy says it is added when the page is published.
  readonly VITE_PRIVACY_CONTACT: string | undefined
}
