// https://nuxt.com/docs/api/configuration/nuxt-config
import { fileURLToPath } from 'node:url'

export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },

  nitro: {
    // Der Builder-Prototyp liegt in frontend/, nicht in public/. Nuxt liefert
    // von sich aus nur public/ statisch aus — die Seite waere sonst gar nicht
    // erreichbar und ihre relativen /api-Aufrufe (window.ENCORE_API) liefen
    // ins Leere. Dieser Eintrag stellt frontend/ zusaetzlich bereit:
    //
    //     http://localhost:3000/encore-builder.html
    //
    // Damit bleibt die Datei, wo sie liegt, und wird trotzdem vom selben
    // Origin wie die API ausgeliefert.
    publicAssets: [
      { baseURL: '/', dir: fileURLToPath(new URL('./frontend', import.meta.url)) },
    ],
  },
})
