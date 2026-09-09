/**
 * GET /api/libraries
 *
 * Returns the pickable module libraries (nanocompartments, cargo presets,
 * linkers, promoters) plus the Type overhang reference — straight out of
 * Biologik/level0_design/data.py, the same source the design itself uses.
 * The frontend populates its decision dropdowns from here instead of
 * hardcoding them, so adding a new nanocompartment (decision 1.2) stays a
 * backend-only change.
 */
import { runBiologik } from '../utils/biologik.js'

export default defineEventHandler(async () => {
  try {
    const { libraries } = await runBiologik('libraries')
    return libraries
  } catch (err) {
    throw createError({ statusCode: 500, statusMessage: err?.message || 'Biologik failed.' })
  }
})
