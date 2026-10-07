/**
 * Bridge to the COMMEC sidecar (biosecurity screening, "Common Mechanism", IBBIS).
 *
 * COMMEC is deliberately NOT part of this Node/Python stack: it needs Conda
 * and BLAST/HMMER (see commec-service/README.md), far too heavy to install
 * automatically like primer3-py/ViennaRNA. Instead it runs
 * as its own container (commec-service/), which starts together with the app by
 * default through Docker Compose (COMMEC_URL points to it by default).
 *
 * Just like primer3/ViennaRNA when missing, this check degrades gracefully:
 * if COMMEC_URL is not set or the service is not (yet) reachable
 * (e.g. while the container is still starting up), {available:false, reason}
 * is returned instead of an error; the design stays usable, only without the
 * security screening.
 */

// A full COMMEC run (biorisk + protein/nucleotide taxonomy) can take several
// minutes according to the IBBIS docs; the timeout has to be generous
// accordingly, otherwise a real, running scan is wrongly counted as
// "not reachable".
const DEFAULT_TIMEOUT_MS = 5 * 60_000

function commecUrl() {
  const url = process.env.COMMEC_URL
  return url ? url.replace(/\/+$/, '') : null
}

// Short timeout: this is a simple "is the container running and are the
// databases there" ping for the status display in the header, not a real screen;
// it must not noticeably delay the page load.
const HEALTH_TIMEOUT_MS = 4_000

/**
 * For the status display in the header ("Biosecurity screening: on/off"): asks
 * GET /health of the sidecar instead of screening a whole sequence.
 *
 * @returns {Promise<{available: boolean, reason?: string}>}
 */
export async function checkCommecHealth() {
  const base = commecUrl()
  if (!base) return { available: false, reason: 'COMMEC_URL is not set.' }

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), HEALTH_TIMEOUT_MS)
  try {
    const res = await fetch(`${base}/health`, { signal: controller.signal })
    if (!res.ok) return { available: false, reason: `commec-service responded ${res.status}` }
    const data = await res.json()
    return data.ok ? { available: true } : { available: false, reason: data.detail || 'Databases not ready yet.' }
  } catch (error) {
    const reason = error.name === 'AbortError'
      ? `commec-service at ${base} did not respond within ${HEALTH_TIMEOUT_MS / 1000}s.`
      : `Could not reach commec-service at ${base}: ${error.message}`
    return { available: false, reason }
  } finally {
    clearTimeout(timer)
  }
}

/**
 * Screen several sequences at once.
 *
 * @param {{label: string, sequence: string}[]} sequences
 * @returns {Promise<{available: boolean, reason?: string, results?: object[]}>}
 *   `results[i]` corresponds to `sequences[i]` and has the form
 *   `{status: {screen_status, biorisk, protein_taxonomy, nucleotide_taxonomy, low_concern, rationale}}`
 *   (see commec-service/app.py for the exact schema).
 */
export async function screenSequences(sequences) {
  const base = commecUrl()
  if (!base) {
    return {
      available: false,
      reason: 'COMMEC_URL is not set: biosecurity screening is disabled. See README.md ("Biosecurity screening is always included") for how to run the commec-service sidecar.',
    }
  }
  if (!Array.isArray(sequences) || sequences.length === 0) {
    return { available: true, results: [] }
  }

  const timeoutMs = Number(process.env.COMMEC_TIMEOUT_MS) || DEFAULT_TIMEOUT_MS
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)

  try {
    const res = await fetch(`${base}/screen`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ sequences }),
      signal: controller.signal,
    })
    if (!res.ok) {
      const detail = await res.text().catch(() => '')
      throw new Error(`commec-service responded ${res.status}${detail ? `: ${detail.slice(0, 300)}` : ''}`)
    }
    const data = await res.json()
    if (!Array.isArray(data.results)) throw new Error('commec-service returned an unexpected shape (no "results" array).')
    return { available: true, results: data.results }
  } catch (error) {
    const reason = error.name === 'AbortError'
      ? `commec-service did not respond within ${Math.round(timeoutMs / 1000)}s.`
      : `Could not reach commec-service at ${base}: ${error.message}`
    return { available: false, reason }
  } finally {
    clearTimeout(timer)
  }
}
