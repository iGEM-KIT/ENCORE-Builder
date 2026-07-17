/**
 * POST /api/cargo/validate
 * Body: { cargoSeq: string }
 *
 * Checks a user-supplied cargo CDS (decision 2.2): length, GC, reading frame,
 * and — crucially — that it does not carry a stop codon (TAA/TAG/TGA) at the
 * end, which would stop translation before the targeting peptide is attached.
 * Returns the full validation object (never throws for a "bad" sequence — an
 * invalid sequence is a valid answer with ok:false).
 */
import { validateCargo } from '../../services/goldenGate/index.js'

export default defineEventHandler(async (event) => {
  const body = await readBody(event)
  const cargoSeq = typeof body?.cargoSeq === 'string' ? body.cargoSeq : ''
  return validateCargo(cargoSeq)
})
