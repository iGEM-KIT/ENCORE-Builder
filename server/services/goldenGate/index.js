/**
 * ENCORE Golden Gate design engine — public entry point.
 *
 * The whole design logic lives in this one folder (data + sequence + design).
 * Import from here everywhere else on the server, e.g.:
 *
 *   import { designConstruct, getLibraries } from '../services/goldenGate/index.js'
 */

export * from './data.js'
export * from './sequence.js'
export { designConstruct, makePrimerPair, buildFasta } from './design.js'

import { CARGO_PRESETS, LINKERS, NANOCOMPARTMENTS, PROMOTERS, TYPE_OVERHANGS } from './data.js'

/**
 * Everything the frontend needs to render the decision dropdowns
 * (nanocompartments, cargo presets, linkers, promoters) plus the Type overhang
 * reference. Kept as a function so it can later read from the database.
 */
export function getLibraries() {
  return {
    nanocompartments: NANOCOMPARTMENTS,
    cargoPresets: CARGO_PRESETS,
    linkers: LINKERS,
    promoters: PROMOTERS,
    typeOverhangs: TYPE_OVERHANGS,
  }
}
