/**
 * GET /api/cargo/commec-status
 *
 * Light health check for the status display in the header ("Biosecurity
 * screening: on/off", next to the dark mode toggle); it only asks whether the
 * COMMEC sidecar is reachable and its databases are ready, and screens
 * no sequence. See server/utils/commec.js.
 */
import { checkCommecHealth } from '../../utils/commec.js'

export default defineEventHandler(async () => {
  return await checkCommecHealth()
})
