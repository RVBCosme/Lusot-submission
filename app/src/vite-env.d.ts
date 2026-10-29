interface ImportMetaEnv {
  // The HTTP API's base URL, from .env.local. It is missing from a build made without that file.
  readonly VITE_API_URL: string | undefined
  // '1' for a release build: the copy-review check then fails while any string is unreviewed (C609).
  readonly VITE_LUSOT_RELEASE: string | undefined
}
