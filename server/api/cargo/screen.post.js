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

export default defineEventHandler(async (event) => {
  const body = await readBody(event)
  const raw = Array.isArray(body?.sequences) ? body.sequences : []
  const sequences = raw
    .map((s) => ({
      label: typeof s?.label === 'string' ? s.label : 'Sequence',
      sequence: typeof s?.sequence === 'string' ? s.sequence.toUpperCase().replace(/[^ATGC]/g, '') : '',
    }))
    .filter((s) => s.sequence.length > 0)

  const screening = await screenSequences(sequences)
  return screening
})
