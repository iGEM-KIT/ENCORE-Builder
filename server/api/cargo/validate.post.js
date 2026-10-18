/**
 * POST /api/cargo/validate
 * Body: { cargoSeq: string, kind?: 'cargo' | 'shell' | 'part' | 'promoter' }
 *   kind 'promoter' checks an own promoter (DNA, length, BsaI/BbsI sites) instead of a CDS.
 *   kind 'shell' / 'part' check a user-supplied nanocompartment shell CDS or a
 *   custom part in a slot next to the shell with the same rules; only the
 *   wording of the stop-codon message differs.
 *
 * Checks a user-supplied cargo CDS (decision 2.2): length, GC, reading frame,
 * and (crucially) that it does not carry a stop codon (TAA/TAG/TGA) at the
 * end, which would stop translation before the targeting peptide is attached.
 *
 * Runs the same validate_cargo() that the design itself uses, so the sequence
 * the user is told is fine is exactly the sequence the design will accept.
 * Returns the full validation object; an invalid sequence is a valid answer
 * with ok:false, not an HTTP error.
 */
import { runBiologik } from '../../utils/biologik.js'

export default defineEventHandler(async (event) => {
  const body = await readBody(event)
  const cargoSeq = typeof body?.cargoSeq === 'string' ? body.cargoSeq : ''
  const kind = ['shell', 'part', 'promoter'].includes(body?.kind) ? body.kind : 'cargo'

  try {
    const { validation } = await runBiologik('validate', { cargoSeq, kind })
    return validation
  } catch (err) {
    throw createError({ statusCode: 500, statusMessage: err?.message || 'Biologik failed.' })
  }
})
