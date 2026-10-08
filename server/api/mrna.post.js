/**
 * POST /api/mrna
 * Body: the same as POST /api/design (nanocompartment, cargoSeq, cargoSlots, ncSlots, ...).
 *
 * mRNA self-fold and self-dimer (ViennaRNA) of the two COMPLETE modules of the design, the cargo module and the nanocompartment
 * module: the mRNA that is translated, from the first coding part to the first stop codon, NCS spacers left out
 * (Biologik/level0_design/mrna_dimer.py: module_mrna). Separate from /api/design because ViennaRNA needs a few seconds for long
 * modules and the design should not wait for it. Returns { cargo, nc }, each with `available` (false + `reason` if ViennaRNA is
 * missing or the module is too long), `length`, `parts`, `endsWithStop`, `selfFold` and `selfDimer`.
 */
import { runBiologik } from '../utils/biologik.js'

export default defineEventHandler(async (event) => {
  const body = (await readBody(event)) || {}

  try {
    const { mrna } = await runBiologik('mrna', {
      nanocompartment: body.nanocompartment,
      customNanocompartment: body.customNanocompartment,
      cargoSeq: body.cargoSeq,
      cargoLabel: body.cargoLabel,
      cargoSlots: body.cargoSlots,
      promoter: body.promoter,
      ncSlots: body.ncSlots,
    })
    return mrna
  } catch (err) {
    if (err?.status === 400) {
      throw createError({ statusCode: 400, statusMessage: err.message })
    }
    throw createError({ statusCode: 500, statusMessage: err?.message || 'Biologik failed.' })
  }
})
