/**
 * POST /api/design
 * Body: {
 *   nanocompartment: string,   // decision 1 (id from /api/libraries, or 'custom')
 *   customNanocompartment?: { label?: string, tp?: string, seq: string },
 *                              // shell CDS + targeting peptide when nanocompartment is 'custom'
 *   cargoSeq: string,          // decision 2 (raw CDS, no trailing stop codon)
 *   cargoLabel?: string,
 *   promoter?: string,         // promoter id (default: GAL1-10)
 *   cargoSlots?: Slots,        // what sits around the cargo (Type 0.1/0.2 behind it, 0.4/0.5 in front)
 *   ncSlots?: Slots,           // what sits around the shell (default: NCS spacer everywhere)
 *   // Slots = { "1" | "2" | "4" | "5": { kind: 'ncs' } | { kind: 'ncsstop' }
 *   //                                | { kind: 'tp' }                    // cargo module, Type 0.1 or 0.5 only
 *   //                                | { kind: 'linker', id: string }
 *   //                                | { kind: 'marker', id: string }    // spycatcher | spytag
 *   //                                | { kind: 'custom', label?: string, seq: string } }
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
 *
 * `cargo.mrnaStructure` (needs ViennaRNA, see Biologik/requirements.txt) checks the cargo's own
 * mRNA for a self-fold (hairpin) and a self-dimer (two copies hybridising) — either can block a
 * scanning ribosome. `available: false` with a `reason` means it was skipped (no ViennaRNA, or the
 * sequence was too long/short); otherwise `selfFold`/`selfDimer` each carry a `deltaG` (kcal/mol)
 * and, for sequences short enough for the shuffled-background z-score, a `risk` grade.
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
