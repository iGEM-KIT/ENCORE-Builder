/**
 * GET /api/libraries
 *
 * Returns the pickable module libraries (nanocompartments, cargo presets,
 * linkers, promoters) plus the Type overhang reference. The frontend can
 * populate its decision dropdowns from here instead of hardcoding them, so
 * adding a new nanocompartment (decision 1.2) becomes a backend-only change.
 */
import { getLibraries } from '../services/goldenGate/index.js'

export default defineEventHandler(() => getLibraries())
