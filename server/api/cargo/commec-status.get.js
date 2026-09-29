/**
 * GET /api/cargo/commec-status
 *
 * Leichter Health-Check fuer die Statusanzeige im Header ("Biosecurity
 * screening: on/off", neben dem Dark-Mode-Toggle) — fragt nur, ob der
 * COMMEC-Sidecar erreichbar ist und seine Datenbanken bereit sind, screent
 * dabei keine Sequenz. Siehe server/utils/commec.js.
 */
import { checkCommecHealth } from '../../utils/commec.js'

export default defineEventHandler(async () => {
  return await checkCommecHealth()
})
