/**
 * Brücke von Nitro zu Biologik (Python).
 *
 * Die gesamte fachliche Logik liegt in `Biologik/` — hier wird nur ein
 * Python-Prozess gestartet, die Nutzlast als JSON auf stdin geschrieben und
 * die Antwort von stdout gelesen. Alle /api-Endpunkte gehen durch diese
 * Funktion, damit Interpreter-Auswahl und Fehlerbehandlung an genau einer
 * Stelle stehen.
 *
 *   import { runBiologik } from '../utils/biologik.js'
 *   const { design } = await runBiologik('design', decisions)
 *
 * Interpreter-Auswahl, in dieser Reihenfolge:
 *   1. BIOLOGIK_PYTHON, falls gesetzt (dann ausschliesslich dieser)
 *   2. ein venv im Projekt (.venv/ oder venv/)
 *   3. python3 / python / py aus dem PATH
 * Jeder Kandidat wird geprueft, bevor er genommen wird — siehe probeCandidates().
 */
import { spawn } from 'node:child_process'
import { resolve } from 'node:path'

const MODULE = 'Biologik.level0_design.cli'

/**
 * Kandidaten für den Python-Interpreter, in dieser Reihenfolge.
 *
 * `python3` und `python` sind unter Windows meist nur die App-Execution-Aliase
 * aus dem Microsoft Store: sie existieren im PATH, starten aber kein Python,
 * sondern geben "Python wurde nicht gefunden" aus. Deshalb wird jeder Kandidat
 * einmal geprüft, statt blind den ersten zu nehmen. `py` ist der Launcher, der
 * unter Windows tatsächlich funktioniert.
 */
const CANDIDATES = ['python3', 'python', 'py']

/**
 * Ein projekteigenes venv gewinnt vor jedem System-Python. Das ist die uebliche
 * Python-Konvention und loest den haeufigsten Fall: Auf dem System liegt ein
 * Python ohne primer3 (oder ohne pip, wie unter Ubuntu mit Python 3.14), und
 * die Abhaengigkeiten stehen stattdessen im venv neben dem Projekt.
 */
const VENV_CANDIDATES = ['.venv/bin/python', '.venv/Scripts/python.exe', 'venv/bin/python']

// Das Promise wird gecacht, nicht erst sein Ergebnis: sonst starten mehrere
// gleichzeitig eintreffende Anfragen die Suche jeweils neu.
let pythonPromise = null

function spawnCollect(command, args, input) {
  return new Promise((resolvePromise, reject) => {
    let child
    try {
      child = spawn(command, args, { cwd: projectRoot() })
    } catch (err) {
      reject(err)
      return
    }
    let stdout = ''
    let stderr = ''
    child.stdout.on('data', (chunk) => { stdout += chunk })
    child.stderr.on('data', (chunk) => { stderr += chunk })
    child.on('error', reject)
    child.on('close', (code) => resolvePromise({ code, stdout, stderr }))
    child.stdin.on('error', () => {}) // Prozess kann stdin schließen, bevor wir schreiben
    child.stdin.end(input ?? '')
  })
}

/**
 * Der cwd bestimmt, ob Python das Paket `Biologik` findet. Im `nuxt dev` ist
 * das die Repo-Wurzel. In einem gebauten Server kann process.cwd() abweichen —
 * dann muss BIOLOGIK_ROOT gesetzt werden.
 */
function projectRoot() {
  return resolve(process.env.BIOLOGIK_ROOT || process.cwd())
}

/**
 * Ersten Kandidaten finden, der wirklich ein Python 3 startet. Ergebnis wird
 * für die Lebensdauer des Servers gemerkt.
 */
async function probeCandidates() {
  const preferred = process.env.BIOLOGIK_PYTHON
  const candidates = preferred
    ? [preferred]
    : [...VENV_CANDIDATES.map((rel) => resolve(projectRoot(), rel)), ...CANDIDATES]

  for (const candidate of candidates) {
    try {
      const probe = await spawnCollect(candidate, ['-c', 'print(1)'], '')
      // Beides pruefen: die Windows-Store-Aliase beenden sich mit Code 0,
      // geben aber nur ihren Hinweistext aus und starten kein Python.
      if (probe.code === 0 && probe.stdout.trim() === '1') return candidate
    } catch {
      // Kandidat existiert nicht — nächster.
    }
  }

  const tried = candidates.join(', ')
  throw Object.assign(
    new Error(
      `No working Python interpreter found (tried: ${tried}). ` +
      `Set BIOLOGIK_PYTHON to the interpreter that has Biologik/requirements.txt installed.`,
    ),
    { status: 500 },
  )
}

function resolvePython() {
  if (!pythonPromise) {
    pythonPromise = probeCandidates().catch((err) => {
      pythonPromise = null   // fehlgeschlagene Suche nicht dauerhaft merken
      throw err
    })
  }
  return pythonPromise
}

/**
 * Ein Biologik-Kommando ausführen.
 *
 * @param {'design'|'libraries'|'validate'} command
 * @param {object} payload  wird als JSON auf stdin geschrieben
 * @returns {Promise<object>} der Inhalt der Antwort ohne das `ok`-Feld
 */
export async function runBiologik(command, payload = {}) {
  const python = await resolvePython()
  const result = await spawnCollect(python, ['-m', MODULE, command], JSON.stringify(payload))

  // stdout ZUERST auswerten: cli.py legt die eigentliche Fehlermeldung dort ab
  // und beendet sich mit Code 1. Wer nur den Exit-Code prüft, wirft genau die
  // Information weg, die dem Nutzer weiterhilft.
  let parsed = null
  try {
    parsed = JSON.parse(result.stdout)
  } catch {
    parsed = null
  }

  if (parsed && parsed.ok === false) {
    throw Object.assign(new Error(parsed.error || 'Biologik rejected the request.'), { status: 400 })
  }

  if (parsed && parsed.ok === true) {
    const { ok, ...rest } = parsed
    return rest
  }

  // Kein verwertbares JSON: echter Absturz, kein Eingabefehler.
  const detail = result.stderr.trim() || result.stdout.trim() || `exit code ${result.code}`
  throw Object.assign(new Error(`Biologik failed: ${detail}`), { status: 500 })
}
