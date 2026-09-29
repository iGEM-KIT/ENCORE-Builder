#!/usr/bin/env node
// Baut encapsulin_selector/selector-data.js aus den einzelnen JSON-Dateien in
// encapsulin_selector/data/ zusammen. Wird automatisch vor `pnpm dev` und
// `pnpm build`/`generate` ausgefuehrt (siehe package.json) — wer einen neuen
// Kandidaten unter data/candidates/<ID>.json hinzufuegt und `pnpm dev`
// startet, sieht ihn sofort im Filter, ohne einen eigenen Befehl zu lernen.
//
// selector-data.js selbst ist GENERIERT und wird trotzdem mit eingecheckt
// (die Selector-Seite wird als reine statische Datei ausgeliefert, siehe
// nuxt.config.ts) — bei einer PR einfach `pnpm build:selector-data` laufen
// lassen und die aktualisierte selector-data.js mit committen.
import { readFileSync, readdirSync, writeFileSync } from 'node:fs'
import { resolve, dirname, basename } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const dataDir = resolve(root, 'encapsulin_selector/data')
const outFile = resolve(root, 'encapsulin_selector/selector-data.js')

const log = (msg) => console.log(`[build-selector-data] ${msg}`)

function readJsonDir(dir) {
  // Dateien, die mit "_" beginnen (z.B. _template.json), sind Vorlagen fuer
  // Beitragende und fliessen nicht in die gebaute Datenbank ein.
  return readdirSync(dir)
    .filter((f) => f.endsWith('.json') && !f.startsWith('_'))
    .sort()
    .map((f) => {
      try {
        return JSON.parse(readFileSync(resolve(dir, f), 'utf8'))
      } catch (error) {
        throw new Error(`${basename(dir)}/${f} ist kein gueltiges JSON: ${error.message}`)
      }
    })
}

// Rundet "~24" oder "24" oder "20-24" in ein fuer den Filter nutzbares
// {min, max, center, approximate, kind} um. Muss von Beitragenden NICHT
// selbst angegeben werden, damit ein neuer Eintrag so einfach wie moeglich
// bleibt (nur das rohe Messwert-Feld ausfuellen).
function deriveShellDiameter(raw) {
  if (raw === null || raw === undefined || raw === '') return null
  if (typeof raw === 'number') {
    return { min: raw, max: raw, center: raw, approximate: false, kind: 'point' }
  }
  const str = String(raw).trim()
  const approximate = str.startsWith('~')
  const cleaned = str.replace('~', '').trim()
  const rangeMatch = cleaned.match(/^(-?\d+(?:\.\d+)?)\s*(?:-|–|to)\s*(-?\d+(?:\.\d+)?)$/)
  if (rangeMatch) {
    const min = parseFloat(rangeMatch[1])
    const max = parseFloat(rangeMatch[2])
    return { min, max, center: (min + max) / 2, approximate, kind: 'range' }
  }
  const num = parseFloat(cleaned)
  if (Number.isFinite(num)) {
    return { min: num, max: num, center: num, approximate, kind: 'point' }
  }
  return null
}

const meta = JSON.parse(readFileSync(resolve(dataDir, 'meta.json'), 'utf8'))
const candidates = readJsonDir(resolve(dataDir, 'candidates'))
const assemblies = readJsonDir(resolve(dataDir, 'assemblies')).map((a) => ({
  ...a,
  _shell_diameter: deriveShellDiameter(a.shell_diameter_nm),
}))

// Konsistenz pruefen, statt eine kaputte Datenbank stillschweigend zu bauen.
const errors = []
const candidateIds = new Set()
for (const c of candidates) {
  if (!c.candidate_id) { errors.push('Ein Kandidat ohne candidate_id gefunden.'); continue }
  if (candidateIds.has(c.candidate_id)) errors.push(`candidate_id "${c.candidate_id}" kommt doppelt vor.`)
  candidateIds.add(c.candidate_id)
}
const assemblyIds = new Set()
for (const a of assemblies) {
  if (!a.assembly_id) { errors.push('Eine Assembly ohne assembly_id gefunden.'); continue }
  if (assemblyIds.has(a.assembly_id)) errors.push(`assembly_id "${a.assembly_id}" kommt doppelt vor.`)
  assemblyIds.add(a.assembly_id)
  if (!candidateIds.has(a.candidate_id)) {
    errors.push(`Assembly "${a.assembly_id}" verweist auf unbekannte candidate_id "${a.candidate_id}".`)
  }
}
for (const c of candidates) {
  if (c.reference_assembly_id && !assemblyIds.has(c.reference_assembly_id)) {
    errors.push(`Kandidat "${c.candidate_id}" verweist mit reference_assembly_id auf unbekannte Assembly "${c.reference_assembly_id}".`)
  }
}

if (errors.length > 0) {
  log('Fehler in encapsulin_selector/data/ — Datenbank wird NICHT gebaut:')
  for (const e of errors) log(`  - ${e}`)
  process.exit(1)
}

// assembly_count pro Kandidat ist immer exakt die Anzahl seiner Assemblies
// (verifiziert gegen den bisherigen Datensatz) — auch dieses Feld muss ein
// neuer Eintrag nicht von Hand pflegen.
const assembliesByCandidate = new Map()
for (const a of assemblies) {
  assembliesByCandidate.set(a.candidate_id, (assembliesByCandidate.get(a.candidate_id) ?? 0) + 1)
}
const candidatesOut = candidates.map((c) => ({
  ...c,
  assembly_count: assembliesByCandidate.get(c.candidate_id) ?? 0,
}))

const data = {
  meta: {
    ...meta,
    candidate_count: candidatesOut.length,
    assembly_count: assemblies.length,
    candidates_with_curated_assemblies: candidatesOut.filter((c) => c.reference_assembly_id).length,
  },
  candidates: candidatesOut,
  assemblies,
}

const banner = '// GENERIERT von scripts/build-selector-data.mjs aus encapsulin_selector/data/ — nicht von Hand editieren.\n// Neue Encapsuline hinzufuegen: siehe encapsulin_selector/data/README.md\n'
writeFileSync(outFile, `${banner}window.ENCAPSULIN_SELECTOR_DATA = ${JSON.stringify(data, null, 2)};\n`)

log(`fertig: ${candidatesOut.length} Kandidaten, ${assemblies.length} Assemblies -> ${basename(outFile)}`)
