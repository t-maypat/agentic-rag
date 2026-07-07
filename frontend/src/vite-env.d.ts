/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_HCAPTCHA_SITE_KEY?: string;
  readonly VITE_GITHUB_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
