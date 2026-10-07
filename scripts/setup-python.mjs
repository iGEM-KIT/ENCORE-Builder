#!/usr/bin/env node
// On the first `pnpm dev` this automatically creates a `.venv` with primer3-py, so that
// nobody has to run `pip install` by hand any more. If any step fails
// (no Python on the PATH, no C compiler for primer3-py, ...), the script does NOT
// abort with an error: Biologik then simply falls back to the less accurate
// Wallace Tm estimate (server/utils/biologik.js).
import { existsSync } from 'node:fs'
import { spawnSync } from 'node:child_process'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const requirements = resolve(root, 'Biologik/requirements.txt')
const venvDir = resolve(root, '.venv')
const isWindows = process.platform === 'win32'
const venvPython = resolve(venvDir, isWindows ? 'Scripts/python.exe' : 'bin/python')
const venvPip = resolve(venvDir, isWindows ? 'Scripts/pip.exe' : 'bin/pip')

const log = (msg) => console.log(`[setup-python] ${msg}`)

if (process.env.BIOLOGIK_PYTHON) {
  log(`BIOLOGIK_PYTHON is set (${process.env.BIOLOGIK_PYTHON}); skipping the automatic venv setup.`)
  process.exit(0)
}

if (!existsSync(requirements)) {
  // Happens e.g. in the Docker build stage if this script ran there before
  // `COPY . .`; the Dockerfile takes care of the installation there anyway.
  log('Biologik/requirements.txt not found; skipping.')
  process.exit(0)
}

if (existsSync(venvPython)) {
  log('.venv already exists; nothing to do (delete .venv to set it up again).')
  process.exit(0)
}

function findSystemPython() {
  for (const cmd of ['python3', 'python', 'py']) {
    const probe = spawnSync(cmd, ['-c', 'print(1)'], { encoding: 'utf8' })
    if (probe.status === 0 && probe.stdout.trim() === '1') return cmd
  }
  return null
}

const systemPython = findSystemPython()
if (!systemPython) {
  log('No Python 3 found on the PATH; Biologik keeps using the Wallace Tm estimate for now. Install Python and start `pnpm dev` again, or set BIOLOGIK_PYTHON.')
  process.exit(0)
}

log(`Creating a virtual environment with ${systemPython} ...`)
const venvResult = spawnSync(systemPython, ['-m', 'venv', venvDir], { stdio: 'inherit', cwd: root })
if (venvResult.status !== 0) {
  log('Creating the venv failed; Biologik keeps using the Wallace Tm estimate for now.')
  process.exit(0)
}

log('Installing primer3-py into .venv (for real Tm/dimer calculation) ...')
const pipResult = spawnSync(venvPip, ['install', '--quiet', '-r', requirements], { stdio: 'inherit', cwd: root })
if (pipResult.status !== 0) {
  log('Installing primer3-py failed (e.g. missing C compiler); Biologik keeps using the Wallace Tm estimate for now. That is harmless, but less accurate.')
  process.exit(0)
}

log('Done: primer3-py is installed in .venv and is found by Biologik automatically.')
