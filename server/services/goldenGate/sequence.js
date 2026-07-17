/**
 * ENCORE Golden Gate — pure DNA sequence utilities.
 *
 * Dependency-free helpers used by the design engine and the cargo-validation
 * endpoint. All functions are pure (no I/O, no state) so they are trivial to
 * unit-test and safe to reuse anywhere on the server.
 *
 * NOTE: melting temperature here is the simplified Wallace rule, matching the
 * UI preview. The authoritative Tm / primer optimisation lives in the Python
 * `Biologik/` pipeline (primer3) and should replace this — see PROJECT_TODO.txt.
 */

import { STOP_CODONS } from './data.js'

const COMPLEMENT = { A: 'T', T: 'A', G: 'C', C: 'G' }

/** Uppercase and strip anything that is not A/T/G/C. */
export const cleanSeq = (s) => (s || '').toUpperCase().replace(/[^ATGC]/g, '')

/** GC content in whole percent (0 for an empty sequence). */
export const gcContent = (s) =>
  s.length ? Math.round((s.replace(/[^GC]/g, '').length / s.length) * 100) : 0

/** Reverse complement (unknown bases -> N). */
export const reverseComplement = (s) =>
  s
    .split('')
    .reverse()
    .map((c) => COMPLEMENT[c] || 'N')
    .join('')

/** Wallace-rule melting temperature: 2 °C per A/T, 4 °C per G/C. */
export const wallaceTm = (s) => {
  const at = (s.match(/[AT]/g) || []).length
  const gc = (s.match(/[GC]/g) || []).length
  return 2 * at + 4 * gc
}

/**
 * Find in-frame stop codons within `seq` (reading frame starts at index 0).
 * Returns [{ pos, codon }] with 0-based nucleotide positions.
 */
export const findInternalStops = (seq) => {
  const hits = []
  for (let i = 0; i + 3 <= seq.length; i += 3) {
    const codon = seq.slice(i, i + 3)
    if (STOP_CODONS.includes(codon)) hits.push({ pos: i, codon })
  }
  return hits
}

/** Return the trailing stop codon (string) if the sequence ends on one, else null. */
export const endsWithStop = (seq) =>
  seq.length >= 3 && STOP_CODONS.includes(seq.slice(-3)) ? seq.slice(-3) : null

/**
 * @typedef {Object} CargoValidation
 * @property {string}  clean            Cleaned A/T/G/C sequence
 * @property {number}  length           Length in bp
 * @property {number}  aa               Approx. amino-acid count (length / 3)
 * @property {number}  gc               GC content (%)
 * @property {number}  invalidChars     Count of ignored non-ATGC characters
 * @property {boolean} notMultipleOfThree
 * @property {?string} trailingStop     Trailing stop codon, or null
 * @property {{pos:number,codon:string}[]} internalStops
 * @property {boolean} ok               True when the CDS is fusion-ready
 * @property {string[]} errors          Blocking problems
 * @property {string[]} warnings        Non-blocking problems
 */

/**
 * Validate a user-supplied cargo CDS.
 *
 * Blocking (ok === false): trailing stop codon, or too short (< 30 bp), or not
 * a multiple of 3. A trailing stop would truncate translation so the targeting
 * peptide never gets attached and the cargo is not encapsulated.
 * Internal in-frame stops are surfaced as a warning (the reading frame may be
 * off) but do not block, matching the prototype behaviour.
 *
 * @param {string} raw  Raw user input (may contain spaces / junk characters)
 * @param {number} [minBp=30]
 * @returns {CargoValidation}
 */
export function validateCargo(raw, minBp = 30) {
  const clean = cleanSeq(raw)
  const length = clean.length
  const invalidChars = (raw || '').toUpperCase().replace(/[ATGC\s]/g, '').length
  const notMultipleOfThree = length % 3 !== 0
  const trailingStop = endsWithStop(clean)
  // exclude the final codon from the internal-stop scan (it is checked separately)
  const internalStops = length >= 3 ? findInternalStops(clean.slice(0, length - 3)) : []

  const errors = []
  const warnings = []

  if (length === 0) {
    errors.push('No valid A/T/G/C sequence provided.')
  } else {
    if (length < minBp) errors.push(`Sequence too short (${length} bp, need at least ${minBp} bp).`)
    if (trailingStop) {
      errors.push(
        `Stop codon at the end (${trailingStop}). Remove it — otherwise the targeting peptide is not attached and the cargo is not encapsulated.`,
      )
    }
    if (notMultipleOfThree) warnings.push('Length is not a multiple of 3 — check the reading frame.')
    if (internalStops.length) {
      const first = internalStops[0]
      warnings.push(`Possible in-frame stop codon at position ${first.pos + 1} (${first.codon}).`)
    }
    if (invalidChars > 0) warnings.push(`${invalidChars} invalid character(s) were ignored.`)
  }

  return {
    clean,
    length,
    aa: Math.floor(length / 3),
    gc: gcContent(clean),
    invalidChars,
    notMultipleOfThree,
    trailingStop,
    internalStops,
    ok: errors.length === 0,
    errors,
    warnings,
  }
}
