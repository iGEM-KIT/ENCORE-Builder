#!/usr/bin/env node
// Builds encapsulin_selector/selector-data.js from the individual JSON files in
// encapsulin_selector/data/. Runs automatically before `pnpm dev` and
// `pnpm build`/`generate` (see package.json); whoever adds a new
// candidate under data/candidates/<ID>.json and starts `pnpm dev`
// sees it in the filter right away, without learning a separate command.
//
// selector-data.js itself is GENERATED and is still committed
// (the selector page is served as a plain static file, see
// nuxt.config.ts); in a PR just run `pnpm build:selector-data`
// and commit the updated selector-data.js as well.
import { readFileSync, readdirSync, writeFileSync } from 'node:fs'
import { resolve, dirname, basename } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const dataDir = resolve(root, 'encapsulin_selector/data')
const outFile = resolve(root, 'encapsulin_selector/selector-data.js')

const log = (msg) => console.log(`[build-selector-data] ${msg}`)

function readJsonDir(dir) {
  // Files that start with "_" (e.g. _template.json) are templates for
  // contributors and do not go into the built database.
  return readdirSync(dir)
    .filter((f) => f.endsWith('.json') && !f.startsWith('_'))
    .sort()
    .map((f) => {
      try {
        return JSON.parse(readFileSync(resolve(dir, f), 'utf8'))
      } catch (error) {
        throw new Error(`${basename(dir)}/${f} is not valid JSON: ${error.message}`)
      }
    })
}

// Turns "~24" or "24" or "20-24" into an {min, max, center, approximate, kind}
// object usable by the filter. Contributors do NOT have to give it
// themselves, so that a new entry stays as simple as possible
// (just fill in the raw measured value field).
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
const sequences = readJsonDir(resolve(dataDir, 'sequences'))
// Check consistency instead of silently building a broken database.
const errors = []
const candidateIds = new Set()
for (const c of candidates) {
  if (!c.candidate_id) { errors.push('Found a candidate without candidate_id.'); continue }
  if (c.candidate_id !== c.candidate_id.trim()) {
    errors.push(`candidate_id "${c.candidate_id}" has a leading/trailing space (almost always a typo).`)
  }
  if (candidateIds.has(c.candidate_id)) errors.push(`candidate_id "${c.candidate_id}" occurs twice.`)
  candidateIds.add(c.candidate_id)
}
const assemblyIds = new Set()
for (const a of assemblies) {
  if (!a.assembly_id) { errors.push('Found an assembly without assembly_id.'); continue }
  if (a.assembly_id !== a.assembly_id.trim()) {
    errors.push(`assembly_id "${a.assembly_id}" has a leading/trailing space (almost always a typo).`)
  }
  if (assemblyIds.has(a.assembly_id)) errors.push(`assembly_id "${a.assembly_id}" occurs twice.`)
  assemblyIds.add(a.assembly_id)
  if (!candidateIds.has(a.candidate_id)) {
    errors.push(`Assembly "${a.assembly_id}" refers to unknown candidate_id "${a.candidate_id}".`)
  }
}
for (const c of candidates) {
  if (c.reference_assembly_id && !assemblyIds.has(c.reference_assembly_id)) {
    errors.push(`Candidate "${c.candidate_id}" refers with reference_assembly_id to unknown assembly "${c.reference_assembly_id}".`)
  }
}

if (errors.length > 0) {
  log('Errors in encapsulin_selector/data/; the database is NOT built:')
  for (const e of errors) log(`  - ${e}`)
  process.exit(1)
}

// assembly_count per candidate is always exactly the number of its assemblies
// (verified against the previous data set); a new entry does not
// have to maintain this field by hand either.
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

const banner = '// GENERATED by scripts/build-selector-data.mjs from encapsulin_selector/data/; do not edit by hand.\n// To add new encapsulins, see encapsulin_selector/data/README.md\n'
writeFileSync(outFile, `${banner}window.ENCAPSULIN_SELECTOR_DATA = ${JSON.stringify(data, null, 2)};\n`)

log(`done: ${candidatesOut.length} candidates, ${assemblies.length} assemblies -> ${basename(outFile)}`)
