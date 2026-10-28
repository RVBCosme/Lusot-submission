interface ImportMetaEnv {
  // The HTTP API's base URL, from .env.local. It is missing from a build made without that file.
  readonly VITE_API_URL: string | undefined
}
