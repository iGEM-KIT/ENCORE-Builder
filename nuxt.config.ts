// https://nuxt.com/docs/api/configuration/nuxt-config
import { fileURLToPath } from 'node:url'

export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },

  nitro: {
    // Der Builder-Prototyp liegt in frontend/, nicht in public/. Nuxt liefert
    // von sich aus nur public/ statisch aus — die Seite waere sonst gar nicht
    // erreichbar und ihre relativen /api-Aufrufe (window.ENCORE_API) liefen
    // ins Leere. Dieser Eintrag stellt frontend/ zusaetzlich bereit.
    //
    // Es gibt keine eigene Vue-Startseite (app/pages/ ist leer) — die Datei
    // heisst deshalb bewusst index.html: der uebliche Static-Server-Fallback
    // liefert sie direkt unter "/" aus (echter 200, kein Redirect/Proxy-Hop).
    publicAssets: [
      { baseURL: '/', dir: fileURLToPath(new URL('./frontend', import.meta.url)) },
      // Das separate Nanocompartment-Finder-Tool, verlinkt von der Builder-
      // Intro-Seite aus ("Before you start" -> /selector/selector-alpha.html).
      { baseURL: '/selector/', dir: fileURLToPath(new URL('./encapsulin_selector', import.meta.url)) },
    ],
  },
})
