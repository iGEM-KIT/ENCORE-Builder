#!/usr/bin/env node
// Copies the OpenDyslexic font files from the npm package @fontsource/opendyslexic (pinned in
// pnpm-lock.yaml) to frontend/fonts/opendyslexic/, where the pages load them from. The font files
// themselves are not committed to the repository. Runs before `pnpm dev`, `pnpm build` and
// `pnpm generate` (see package.json).
import { copyFileSync, existsSync, mkdirSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const from = resolve(root, 'node_modules/@fontsource/opendyslexic/files')
const to = resolve(root, 'frontend/fonts/opendyslexic')

const files = {
  'opendyslexic-latin-400-normal.woff2': 'opendyslexic-regular.woff2',
  'opendyslexic-latin-700-normal.woff2': 'opendyslexic-bold.woff2',
  'opendyslexic-latin-400-italic.woff2': 'opendyslexic-italic.woff2',
  'opendyslexic-latin-700-italic.woff2': 'opendyslexic-bolditalic.woff2',
}

if (!existsSync(from)) {
  console.error('[copy-fonts] @fontsource/opendyslexic is not installed. Run `pnpm install` first.')
  process.exit(1)
}
mkdirSync(to, { recursive: true })
for (const [source, target] of Object.entries(files)) copyFileSync(resolve(from, source), resolve(to, target))
console.log('[copy-fonts] OpenDyslexic copied to frontend/fonts/opendyslexic/')
