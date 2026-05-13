/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string
  readonly VITE_WS_BASE_URL: string
  readonly VITE_APP_TITLE: string
  readonly VITE_MOCK_MODE: string
  readonly VITE_ENV_NAME: string
  readonly VITE_ENV_DESCRIPTION: string
  readonly VITE_ENV_COLOR: string
  readonly VITE_ENV_ICON: string
  readonly VITE_MOCK_API: string
  readonly VITE_APP_NAME: string
  readonly VITE_APP_VERSION: string
  readonly VITE_APP_DESCRIPTION: string
  readonly VITE_APP_AUTHOR: string
  readonly VITE_APP_LICENSE: string
  readonly VITE_APP_HOMEPAGE: string
  readonly VITE_APP_REPOSITORY: string
  readonly VITE_APP_BUGS: string
  readonly VITE_APP_DOCS: string
  readonly VITE_APP_SUPPORT: string
  readonly VITE_APP_PRIVACY: string
  readonly VITE_APP_TERMS: string
  readonly VITE_APP_COPYRIGHT: string
  readonly VITE_APP_LOGO: string
  readonly VITE_APP_FAVICON: string
  readonly VITE_APP_OG_IMAGE: string
  readonly VITE_APP_OG_TITLE: string
  readonly VITE_APP_OG_DESCRIPTION: string
  readonly VITE_APP_OG_URL: string
  readonly VITE_APP_OG_TYPE: string
  readonly VITE_APP_OG_SITE_NAME: string
  readonly VITE_APP_OG_LOCALE: string
  readonly VITE_APP_TWITTER_CARD: string
  readonly VITE_APP_TWITTER_SITE: string
  readonly VITE_APP_TWITTER_CREATOR: string
  readonly VITE_APP_TWITTER_IMAGE: string
  readonly VITE_APP_TWITTER_TITLE: string
  readonly VITE_APP_TWITTER_DESCRIPTION: string
  readonly VITE_APP_TWITTER_URL: string
  readonly VITE_APP_TWITTER_TYPE: string
  readonly VITE_APP_TWITTER_SITE_NAME: string
  readonly VITE_APP_TWITTER_LOCALE: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
