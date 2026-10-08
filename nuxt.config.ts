// https://nuxt.com/docs/api/configuration/nuxt-config
import { fileURLToPath } from 'node:url'

export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },

  nitro: {
    // The static pages and scripts (frontend/, encapsulin_selector/) carry no cache header of their own, so browsers cache
    // them heuristically and keep showing an old version after an update. "no-cache" makes the browser ask the server
    // each time (answered with a cheap 304 while nothing changed).
    routeRules: { '/**': { headers: { 'cache-control': 'no-cache' } } },

    // The builder prototype lives in frontend/, not in public/. By itself Nuxt
    // only serves public/ statically; the page would not be reachable at all
    // and its relative /api calls (window.ENCORE_API) would go
    // nowhere. This entry makes frontend/ available as well.
    //
    // There is no Vue start page of its own (app/pages/ is empty), so the file
    // is deliberately called index.html: the usual static server fallback
    // serves it directly at "/" (a real 200, no redirect/proxy hop).
    publicAssets: [
      { baseURL: '/', dir: fileURLToPath(new URL('./frontend', import.meta.url)) },
      // The separate nanocompartment finder tool, linked from the builder
      // intro page (the filter link, /selector/selector-alpha.html).
      { baseURL: '/selector/', dir: fileURLToPath(new URL('./encapsulin_selector', import.meta.url)) },
    ],
  },
})
