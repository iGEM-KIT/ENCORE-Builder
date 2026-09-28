/**
 * POST /api/design
 * Body: {
 *   nanocompartment: string,   // decision 1 (id from /api/libraries, or 'custom')
 *   customNanocompartment?: { label?: string, tp?: string, seq: string },
 *                              // shell CDS + targeting peptide when nanocompartment is 'custom'
 *   cargoSeq: string,          // decision 2 (raw CDS, no trailing stop codon)
 *   fusion: 'C' | 'N',         // decision 3
 *   cargoLabel?: string,
 *   linker?: string,           // linker id (default: first in library)
 *   promoter?: string,         // promoter id (default: GAL1-10)
 *   ncSlots?: {                // what sits next to the shell (default: NCS spacer everywhere)
 *     "1" | "2" | "4" | "5": { kind: 'ncs' }
 *                          | { kind: 'linker', id: string }
 *                          | { kind: 'marker', id: string }        // spycatcher | spytag
 *                          | { kind: 'custom', label?: string, seq: string }
 *   }
 *   fasta?: boolean            // also return a FASTA export string
 * }
 *
 * Runs the Golden Gate design in Biologik (Python) and returns the full
 * assembly plan: 10 Level 0 parts (with Type overhangs), 2 Level 1 modules,
 * the Level 2 construct, cargo primers, the 96-well pick plan and the order
 * list.
 *
 * The primers carry `tmMethod`: 'primer3-nn' means real nearest-neighbor
 * thermodynamics (plus q5AnnealingTemp), 'wallace' means primer3 was not
 * available on the server and the values are rough estimates — `warnings`
 * then says so.
 */
import { runBiologik } from '../utils/biologik.js'

export default defineEventHandler(async (event) => {
  const body = (await readBody(event)) || {}

  try {
    const { design } = await runBiologik('design', {
      nanocompartment: body.nanocompartment,
      customNanocompartment: body.customNanocompartment,
      cargoSeq: body.cargoSeq,
      cargoLabel: body.cargoLabel,
      fusion: body.fusion,
      linker: body.linker,
      promoter: body.promoter,
      ncSlots: body.ncSlots,
      fasta: Boolean(body.fasta),
    })
    return design
  } catch (err) {
    // Biologik reports invalid input with .status = 400 and a message that
    // explains what is wrong — pass it through instead of a generic string.
    if (err?.status === 400) {
      throw createError({ statusCode: 400, statusMessage: err.message })
    }
    throw createError({ statusCode: 500, statusMessage: err?.message || 'Biologik failed.' })
  }
})
