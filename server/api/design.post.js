/**
 * POST /api/design
 * Body: {
 *   nanocompartment: string,   // decision 1 (id from /api/libraries)
 *   cargoSeq: string,          // decision 2 (raw CDS, no trailing stop codon)
 *   fusion: 'C' | 'N',         // decision 3
 *   cargoLabel?: string,
 *   linker?: string,           // linker id (default: first in library)
 *   promoter?: string,         // promoter id (default: GAL1-10)
 *   fasta?: boolean            // also return a FASTA export string
 * }
 *
 * Runs the Golden Gate design and returns the full assembly plan: 10 Level 0
 * parts (with Type overhangs), 2 Level 1 modules, the Level 2 construct,
 * cargo primers, the 96-well pick plan and the order list.
 */
import { buildFasta, designConstruct } from '../services/goldenGate/index.js'

export default defineEventHandler(async (event) => {
  const body = (await readBody(event)) || {}

  let design
  try {
    design = designConstruct({
      nanocompartment: body.nanocompartment,
      cargoSeq: body.cargoSeq,
      cargoLabel: body.cargoLabel,
      fusion: body.fusion,
      linker: body.linker,
      promoter: body.promoter,
    })
  } catch (err) {
    // The engine throws a plain Error with .status = 400 for invalid input.
    if (err?.status === 400) {
      throw createError({ statusCode: 400, statusMessage: err.message, data: err.data })
    }
    throw err
  }

  if (body.fasta) design.fasta = buildFasta(design)
  return design
})
