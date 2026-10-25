/// <reference types="vite/client" />

interface ImportMetaEnv {
  // Mobile app only: absolute API origin, e.g. https://panel.guaynet.com.ar
  readonly VITE_API_BASE_URL?: string;
  // Mobile app only: "true" when the Android project has google-services.json
  readonly VITE_PUSH_ENABLED?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
