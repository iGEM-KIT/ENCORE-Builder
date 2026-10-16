#!/usr/bin/env node
// Builds encapsulin_selector/selector-data.js from the individual JSON files in
// encapsulin_selector/data/. Runs automatically before `pnpm dev` and
// `pnpm build`/`generate` (see package.json). Curated data should be
// updated in the master Excel and exported to JSON via
// scripts/export-excel-to-json.py before rebuilding this file.
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
const pores = readJsonDir(resolve(dataDir, 'pores'))
const evidence = readJsonDir(resolve(dataDir, 'evidence'))
const doiIndex = JSON.parse(readFileSync(resolve(dataDir, 'doi_index.json'), 'utf8'))
const citationLinks = JSON.parse(readFileSync(resolve(dataDir, 'citation_links.json'), 'utf8'))
const vocabularies = JSON.parse(readFileSync(resolve(dataDir, 'vocabularies.json'), 'utf8'))
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
const sequenceIds = new Set()

for (const s of sequences) {
  if (!s.sequence_link_id) {
    errors.push('Found a sequence without sequence_link_id.')
    continue
  }

  if (s.sequence_link_id !== s.sequence_link_id.trim()) {
    errors.push(
      `sequence_link_id "${s.sequence_link_id}" has a leading/trailing space (almost always a typo).`
    )
  }

  if (sequenceIds.has(s.sequence_link_id)) {
    errors.push(`sequence_link_id "${s.sequence_link_id}" occurs twice.`)
  }

  sequenceIds.add(s.sequence_link_id)

  if (!candidateIds.has(s.candidate_id)) {
    errors.push(
      `Sequence "${s.sequence_link_id}" refers to unknown candidate_id "${s.candidate_id}".`
    )
  }
}
for (const c of candidates) {
  if (c.reference_assembly_id && !assemblyIds.has(c.reference_assembly_id)) {
    errors.push(`Candidate "${c.candidate_id}" refers with reference_assembly_id to unknown assembly "${c.reference_assembly_id}".`)
  }
}

// Every pore state is associated with a candidate and, where curated, an assembly.
const poresById = new Map()
for (const p of pores) {
  if (!p.pore_record_id || typeof p.pore_record_id !== 'string') {
    errors.push('Found a pore without pore_record_id.')
    continue
  }
  if (poresById.has(p.pore_record_id)) errors.push(`Duplicate pore_record_id "${p.pore_record_id}".`)
  poresById.set(p.pore_record_id, p)
  if (!candidateIds.has(p.candidate_id)) {
    errors.push(`Pore "${p.pore_record_id}" refers to unknown candidate_id "${p.candidate_id}".`)
  }
  if (p.assembly_id) {
    if (!assemblyIds.has(p.assembly_id)) {
      errors.push(`Pore "${p.pore_record_id}" refers to unknown assembly_id "${p.assembly_id}".`)
    } else {
      const parent = assemblies.find(a => a.assembly_id === p.assembly_id)
      if (parent.candidate_id !== p.candidate_id) {
        errors.push(`Pore "${p.pore_record_id}" has a different candidate_id from assembly "${p.assembly_id}".`)
      }
    }
  }
}

const evidenceIds = new Set()
for (const e of evidence) {
  if (!e.evidence_id || typeof e.evidence_id !== 'string') {
    errors.push('Found an evidence record without evidence_id.')
    continue
  }
  if (evidenceIds.has(e.evidence_id)) errors.push(`Duplicate evidence_id "${e.evidence_id}".`)
  evidenceIds.add(e.evidence_id)
  if (!candidateIds.has(e.candidate_id)) {
    errors.push(`Evidence "${e.evidence_id}" refers to unknown candidate_id "${e.candidate_id}".`)
  }
}

const doiIds = new Set()
for (const d of doiIndex) {
  if (!d.doi || typeof d.doi !== 'string') {
    errors.push('Found a doi_index entry without DOI.')
    continue
  }
  if (doiIds.has(d.doi)) errors.push(`Duplicate DOI "${d.doi}" in doi_index.`)
  doiIds.add(d.doi)
}

// Join citations by DOI (not citation_label: spellings and abbreviations vary).
const idsByTable = {
  databank: candidateIds,
  assemblies: assemblyIds,
  pores: new Set(poresById.keys()),
  evidence: evidenceIds,
}
const linksByDoi = new Map()
const citationKeys = new Set()
for (const link of citationLinks) {
  const tableIds = idsByTable[link.table]
  if (!tableIds) {
    errors.push(`Unknown citation table "${link.table}".`)
    continue
  }
  if (!tableIds.has(link.record_id)) {
    errors.push(`Citation refers to unknown ${link.table} record "${link.record_id}".`)
  }
  if (!candidateIds.has(link.candidate_id)) {
    errors.push(`Citation for "${link.record_id}" has unknown candidate_id "${link.candidate_id}".`)
  }
  if (!doiIds.has(link.doi)) {
    errors.push(`Citation for "${link.record_id}" refers to DOI "${link.doi}" missing from doi_index.`)
  }
  const duplicateKey = `${link.table}\u0000${link.record_id}\u0000${link.doi}`
  if (citationKeys.has(duplicateKey)) {
    errors.push(`Duplicate citation: ${link.table}/${link.record_id}/${link.doi}.`)
  }
  citationKeys.add(duplicateKey)
  linksByDoi.set(link.doi, (linksByDoi.get(link.doi) ?? 0) + 1)
  const owner = link.table === 'databank'
    ? candidates.find(c => c.candidate_id === link.record_id)
    : link.table === 'assemblies'
      ? assemblies.find(a => a.assembly_id === link.record_id)
      : link.table === 'pores'
        ? poresById.get(link.record_id)
        : evidence.find(e => e.evidence_id === link.record_id)
  if (owner && owner.candidate_id !== link.candidate_id) {
    errors.push(`Citation ${link.table}/${link.record_id} has an inconsistent candidate_id.`)
  }
}
for (const d of doiIndex) {
  if (d.linked_record_count !== undefined && d.linked_record_count !== null &&
      d.linked_record_count !== (linksByDoi.get(d.doi) ?? 0)) {
    errors.push(`DOI "${d.doi}" link count differs from citation_links.`)
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
const sequencesByCandidate = new Map()

for (const s of sequences) {
  sequencesByCandidate.set(
    s.candidate_id,
    (sequencesByCandidate.get(s.candidate_id) ?? 0) + 1
  )
}
const candidatesOut = candidates.map((c) => ({
  ...c,
  assembly_count: assembliesByCandidate.get(c.candidate_id) ?? 0,
  sequence_count: sequencesByCandidate.get(c.candidate_id) ?? 0,
}))

const data = {
  meta: {
    ...meta,
    candidate_count: candidatesOut.length,
    assembly_count: assemblies.length,
    sequence_count: sequences.length,
    pore_count: pores.length,
    evidence_count: evidence.length,
    doi_count: doiIndex.length,
    citation_link_count: citationLinks.length,
    candidates_with_curated_assemblies: candidatesOut.filter((c) => c.reference_assembly_id).length,
  },
  candidates: candidatesOut,
  assemblies,
  sequences,
  pores,
  evidence,
  doi_index: doiIndex,
  citation_links: citationLinks,
  vocabularies,
}

const banner = '// GENERATED by scripts/build-selector-data.mjs from encapsulin_selector/data/; do not edit by hand.\n// To add new encapsulins, see encapsulin_selector/data/README.md\n'
writeFileSync(outFile, `${banner}window.ENCAPSULIN_SELECTOR_DATA = ${JSON.stringify(data, null, 2)};\n`)

// Builder Filter is an approved sequence catalog, separate from the scientific explorer.
const builderCatalog = JSON.parse(readFileSync(resolve(dataDir,'builder_catalog.json'),'utf8'))
if (!Array.isArray(builderCatalog) || builderCatalog.length !== 24) {
  throw new Error('Expected exactly 24 reviewed Builder shell designs.')
}
const catalogIds = new Set()
for (const d of builderCatalog) {
  if (catalogIds.has(d.sequence_id)) throw new Error(`Duplicate Builder sequence ${d.sequence_id}`)
  catalogIds.add(d.sequence_id)
  if (d.translation_qc !== 'PASS' || !candidateIds.has(d.candidate_id) || !assemblyIds.has(d.assembly_id))
    throw new Error(`Unapproved or orphaned Builder design ${d.sequence_id}`)
  const a = assemblies.find(x => x.assembly_id === d.assembly_id)
  if (a.candidate_id !== d.candidate_id) throw new Error(`Mismatched Builder candidate ${d.sequence_id}`)
  if (!/^[ACGT]+$/.test(d.cds) || d.cds.length !== d.cds_length_nt || d.cds.length % 3 !== 0)
    throw new Error(`Invalid Builder CDS ${d.sequence_id}`)
}
writeFileSync(resolve(root, 'encapsulin_selector/builder-catalog.js'),
  `// GENERATED. Do not edit manually.\nwindow.ENCORE_BUILDER_CATALOG = ${JSON.stringify(builderCatalog, null, 2)};\n`)


log(
  `done: ${candidatesOut.length} candidates, ${assemblies.length} assemblies, ${sequences.length} sequences, ${pores.length} pores, ${evidence.length} evidence, ${doiIndex.length} DOIs, ${citationLinks.length} citation links -> ${basename(outFile)}`
)
