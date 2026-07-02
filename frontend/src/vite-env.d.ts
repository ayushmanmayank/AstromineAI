/// <reference types="vite/client" />

// Vite environment variable declarations for AstroMineAI frontend configuration.
interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_USE_MOCK_API?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
