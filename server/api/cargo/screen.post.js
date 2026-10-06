/**
 * POST /api/cargo/screen
 * Body: { sequences: {label: string, sequence: string}[] }
 *
 * Biosecurity screening of every user-entered CDS (cargo, custom shell, custom
 * module parts) via the optional COMMEC sidecar (server/utils/commec.js) — so
 * a design cannot be built from a sequence that matches a regulated pathogen
 * or known virulence factor without the user explicitly acknowledging it.
 *
 * A missing/unreachable screening service is a valid, non-error response
 * (available:false) — the frontend then shows that screening did not run,
 * it does not block the builder. Only sequences are sent, one per item;
 * unknown fields in the body are ignored.
 */
import { screenSequences } from '../../utils/commec.js'

// Most frequent S. cerevisiae codon per amino acid (Kazusa) — only used to give an amino acid sequence a DNA form for the
// screen: COMMEC translates in all frames, so any back-translation of the protein is screened equivalently.
const BEST_CODON = {
  A: 'GCT', C: 'TGT', D: 'GAT', E: 'GAA', F: 'TTT', G: 'GGT', H: 'CAT', I: 'ATT', K: 'AAA', L: 'TTG',
  M: 'ATG', N: 'AAT', P: 'CCA', Q: 'CAA', R: 'AGA', S: 'TCT', T: 'ACT', V: 'GTT', W: 'TGG', Y: 'TAT', '*': 'TAA',
}

// Same rule as is_protein() in Biologik/level0_design/sequence.py: DNA if at least 90 % of the letters are A/C/G/T/U/N.
function toDna(text) {
  const letters = text.toUpperCase().replace(/^>.*$/gm, '').replace(/[^A-Z*]/g, '')
  const dnaLetters = (letters.match(/[ACGTUN]/g) || []).length
  if (letters && dnaLetters / letters.length < 0.9) {
    return letters.split('').map((aa) => BEST_CODON[aa] || '').join('')
  }
  return letters.replace(/[^ATGC]/g, '')
}

export default defineEventHandler(async (event) => {
  const body = await readBody(event)
  const raw = Array.isArray(body?.sequences) ? body.sequences : []
  const sequences = raw
    .map((s) => ({
      label: typeof s?.label === 'string' ? s.label : 'Sequence',
      sequence: typeof s?.sequence === 'string' ? toDna(s.sequence) : '',
    }))
    .filter((s) => s.sequence.length > 0)

  const screening = await screenSequences(sequences)
  return screening
})
