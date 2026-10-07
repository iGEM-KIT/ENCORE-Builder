/**
 * Bridge from Nitro to Biologik (Python).
 *
 * All the scientific logic lives in `Biologik/`; here only a Python process is
 * started, the payload is written to stdin as JSON and the answer is read from
 * stdout. All /api endpoints go through this function, so that interpreter
 * selection and error handling are in exactly one place.
 *
 *   import { runBiologik } from '../utils/biologik.js'
 *   const { design } = await runBiologik('design', decisions)
 *
 * Interpreter selection, in this order:
 *   1. BIOLOGIK_PYTHON, if set (then only this one)
 *   2. a venv in the project (.venv/ or venv/)
 *   3. python3 / python / py from the PATH
 * Every candidate is checked before it is taken, see probeCandidates().
 */
import { spawn } from 'node:child_process'
import { resolve } from 'node:path'

const MODULE = 'Biologik.level0_design.cli'

/**
 * Candidates for the Python interpreter, in this order.
 *
 * On Windows `python3` and `python` are usually only the app execution aliases
 * from the Microsoft Store: they exist on the PATH but do not start Python,
 * they print "Python was not found" instead. That is why every candidate is
 * checked once, instead of blindly taking the first one. `py` is the launcher
 * that actually works on Windows.
 */
const CANDIDATES = ['python3', 'python', 'py']

/**
 * A venv of the project wins over any system Python. That is the usual
 * Python convention and solves the most common case: the system has a
 * Python without primer3 (or without pip, as on Ubuntu with Python 3.14), and
 * the dependencies are in the venv next to the project instead.
 */
const VENV_CANDIDATES = ['.venv/bin/python', '.venv/Scripts/python.exe', 'venv/bin/python']

// The promise is cached, not only its result: otherwise several requests
// arriving at the same time would each start the search again.
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
    child.stdin.on('error', () => {}) // the process may close stdin before we write
    child.stdin.end(input ?? '')
  })
}

/**
 * The cwd decides whether Python finds the package `Biologik`. In `nuxt dev` it
 * is the repo root. In a built server process.cwd() may differ;
 * then BIOLOGIK_ROOT has to be set.
 */
function projectRoot() {
  return resolve(process.env.BIOLOGIK_ROOT || process.cwd())
}

/**
 * Find the first candidate that really starts a Python 3. The result is
 * remembered for the lifetime of the server.
 */
async function probeCandidates() {
  const preferred = process.env.BIOLOGIK_PYTHON
  const candidates = preferred
    ? [preferred]
    : [...VENV_CANDIDATES.map((rel) => resolve(projectRoot(), rel)), ...CANDIDATES]

  for (const candidate of candidates) {
    try {
      const probe = await spawnCollect(candidate, ['-c', 'print(1)'], '')
      // Check both: the Windows Store aliases exit with code 0
      // but only print their hint text and do not start Python.
      if (probe.code === 0 && probe.stdout.trim() === '1') return candidate
    } catch {
      // candidate does not exist; try the next one.
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
      pythonPromise = null   // do not remember a failed search permanently
      throw err
    })
  }
  return pythonPromise
}

/**
 * Run a Biologik command.
 *
 * @param {'design'|'libraries'|'validate'|'to_dna'} command
 * @param {object} payload  written to stdin as JSON
 * @returns {Promise<object>} the content of the answer without the `ok` field
 */
export async function runBiologik(command, payload = {}) {
  const python = await resolvePython()
  const result = await spawnCollect(python, ['-m', MODULE, command], JSON.stringify(payload))

  // Read stdout FIRST: cli.py puts the actual error message there
  // and exits with code 1. Anyone who only checks the exit code throws away exactly
  // the information that helps the user.
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

  // No usable JSON: a real crash, not an input error.
  const detail = result.stderr.trim() || result.stdout.trim() || `exit code ${result.code}`
  throw Object.assign(new Error(`Biologik failed: ${detail}`), { status: 500 })
}
