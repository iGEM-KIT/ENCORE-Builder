/**
 * Brücke zum COMMEC-Sidecar (Biosicherheits-Screening, "Common Mechanism", IBBIS).
 *
 * COMMEC ist bewusst NICHT Teil dieses Node/Python-Stacks: es braucht Conda
 * und BLAST/HMMER (siehe commec-service/README.md) — viel zu schwer, um es
 * wie primer3-py/ViennaRNA automatisch mitzuinstallieren. Stattdessen läuft
 * es als eigener Container (commec-service/), der per Docker Compose standard-
 * mäßig zusammen mit der App startet (COMMEC_URL zeigt per Default darauf).
 *
 * Genau wie primer3/ViennaRNA beim Fehlen degradiert dieser Check graziös:
 * ist COMMEC_URL nicht gesetzt oder der Service (noch) nicht erreichbar
 * (z. B. während der Container erst hochfährt), wird {available:false, reason}
 * zurückgegeben statt eines Fehlers — das Design bleibt nutzbar, nur ohne das
 * Sicherheits-Screening.
 */

// Ein voller COMMEC-Lauf (Biorisk + Protein-/Nukleotid-Taxonomie) kann laut
// IBBIS-Doku mehrere Minuten dauern — das Timeout muss entsprechend grosszuegig
// sein, sonst wird ein echter, laufender Scan faelschlich als "nicht erreichbar"
// gewertet.
const DEFAULT_TIMEOUT_MS = 5 * 60_000

function commecUrl() {
  const url = process.env.COMMEC_URL
  return url ? url.replace(/\/+$/, '') : null
}

// Kurzer Timeout: das ist ein simpler "laeuft der Container und sind die
// Datenbanken da"-Ping fuer die Status-Anzeige im Header, kein echter Screen —
// soll die Seite beim Laden nicht spuerbar verzoegern.
const HEALTH_TIMEOUT_MS = 4_000

/**
 * Fuer die Status-Anzeige im Header ("Biosecurity screening: on/off"): fragt
 * GET /health des Sidecars ab, statt eine ganze Sequenz zu screenen.
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
 * Mehrere Sequenzen auf einmal screenen.
 *
 * @param {{label: string, sequence: string}[]} sequences
 * @returns {Promise<{available: boolean, reason?: string, results?: object[]}>}
 *   `results[i]` korrespondiert zu `sequences[i]` und hat die Form
 *   `{status: {screen_status, biorisk, protein_taxonomy, nucleotide_taxonomy, low_concern, rationale}}`
 *   — siehe commec-service/app.py für das genaue Schema.
 */
export async function screenSequences(sequences) {
  const base = commecUrl()
  if (!base) {
    return {
      available: false,
      reason: 'COMMEC_URL is not set — biosecurity screening is disabled. See README.md ("Biosicherheits-Screening ist immer dabei") for how to run the commec-service sidecar.',
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
