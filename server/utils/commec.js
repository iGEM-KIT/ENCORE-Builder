/**
 * Brücke zum COMMEC-Sidecar (Biosicherheits-Screening, "Common Mechanism", IBBIS).
 *
 * COMMEC ist bewusst NICHT Teil dieses Node/Python-Stacks: es braucht Conda,
 * BLAST/HMMER und ~40GB Referenzdatenbanken (siehe commec-service/README.md) —
 * viel zu schwer, um es wie primer3-py/ViennaRNA automatisch mitzuinstallieren.
 * Stattdessen läuft es als optionaler eigener Container (commec-service/), den
 * die App per HTTP anspricht, wenn COMMEC_URL gesetzt ist.
 *
 * Genau wie primer3/ViennaRNA beim Fehlen degradiert dieser Check graziös:
 * ist COMMEC_URL nicht gesetzt oder der Service nicht erreichbar, wird
 * {available:false, reason} zurückgegeben statt eines Fehlers — das Design
 * bleibt nutzbar, nur ohne das Sicherheits-Screening.
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
      reason: 'COMMEC_URL is not set — biosecurity screening is disabled. See README.md ("Biosecurity screening") for how to run the commec-service sidecar.',
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
