/**
 * POST /api/design
 * Body: {
 *   nanocompartment: string,   // decision 1 (id from /api/libraries, or 'custom')
 *   customNanocompartment?: { label?: string, tp?: string, seq: string },
 *                              // shell CDS + targeting peptide when nanocompartment is 'custom'
 *   cargoSeq: string,          // decision 2 (raw CDS (DNA) or amino acid sequence, no trailing stop codon)
 *   cargoLabel?: string,
 *   promoter?: string,         // promoter id (default: GAL1-10)
 *   cargoSlots?: Slots,        // what sits around the cargo (Type 0.1/0.2 behind it, 0.4/0.5 in front)
 *   ncSlots?: Slots,           // what sits around the shell (default: NCS spacer everywhere)
 *   // Slots = { "1" | "2" | "4" | "5": { kind: 'ncs' }
 *   //                                | { kind: 'tp' }                    // cargo module, Type 0.1 or 0.5 only
 *   //                                | { kind: 'linker', id: string }
 *   //                                | { kind: 'marker', id: string }    // spycatcher | spytag
 *   //                                | { kind: 'custom', label?: string, seq: string } }

 *   optimizeToolkit?: boolean, // also optimize the sequences of the toolKIT again (yeast codon usage, no RFC 10 / RFC 1000 sites)
 *   genbank?: boolean          // also return a GenBank export string (annotated; see design.py: build_genbank)
 * }
 *
 * Runs the Golden Gate design in Biologik (Python) and returns what the Builder UI shows:
 * nanocompartment, targetingPeptide, cargo, the 10 Level 0 parts (`level0`), the promoter (`level2`),
 * the slot summaries (`cargoSlots`/`ncSlots`), the cargo `primers`, `level0Constructs` (every module's
 * part inside its type adapter plus the plasmid it is BbsI-cloned into, each with a ready GenBank text)
 * and, with `genbank: true`, the annotated GenBank export (`genbank`).
 *
 * The primers carry `tmMethod`: 'primer3-nn' means real nearest-neighbor thermodynamics (plus
 * q5AnnealingTemp), 'wallace' means primer3 was not available on the server and the values are rough
 * estimates.
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
      cargoSlots: body.cargoSlots,
      promoter: body.promoter,
      ncSlots: body.ncSlots,
      optimizeToolkit: Boolean(body.optimizeToolkit),
      genbank: Boolean(body.genbank),
    })
    return design
  } catch (err) {
    // Biologik reports invalid input with .status = 400 and a message that
    // explains what is wrong; pass it through instead of a generic string.
    if (err?.status === 400) {
      throw createError({ statusCode: 400, statusMessage: err.message })
    }
    throw createError({ statusCode: 500, statusMessage: err?.message || 'Biologik failed.' })
  }
})
