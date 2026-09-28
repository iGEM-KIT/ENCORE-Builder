#!/usr/bin/env node
// Legt beim ersten `pnpm dev` automatisch ein `.venv` mit primer3-py an, damit
// niemand mehr manuell `pip install` ausfuehren muss. Schlaegt irgendein
// Schritt fehl (kein Python im PATH, kein C-Compiler fuer primer3-py, ...),
// bricht das Skript NICHT mit einem Fehler ab: Biologik faellt dann einfach
// auf die ungenauere Wallace-Tm-Schaetzung zurueck (server/utils/biologik.js).
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
  log(`BIOLOGIK_PYTHON ist gesetzt (${process.env.BIOLOGIK_PYTHON}) — ueberspringe automatisches venv-Setup.`)
  process.exit(0)
}

if (!existsSync(requirements)) {
  // Passiert z.B. in der Docker-Build-Stage, falls dieses Skript dort vor
  // `COPY . .` liefe — dort uebernimmt ohnehin das Dockerfile die Installation.
  log('Biologik/requirements.txt nicht gefunden — ueberspringe.')
  process.exit(0)
}

if (existsSync(venvPython)) {
  log('.venv existiert bereits — nichts zu tun (zum Neuaufsetzen .venv loeschen).')
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
  log('Kein Python 3 im PATH gefunden — Biologik nutzt bis auf Weiteres die Wallace-Tm-Schaetzung. Python installieren und `pnpm dev` erneut starten, oder BIOLOGIK_PYTHON setzen.')
  process.exit(0)
}

log(`Lege virtuelle Umgebung an mit ${systemPython} ...`)
const venvResult = spawnSync(systemPython, ['-m', 'venv', venvDir], { stdio: 'inherit', cwd: root })
if (venvResult.status !== 0) {
  log('venv-Erstellung fehlgeschlagen — Biologik nutzt bis auf Weiteres die Wallace-Tm-Schaetzung.')
  process.exit(0)
}

log('Installiere primer3-py in .venv (fuer echte Tm/Dimer-Berechnung) ...')
const pipResult = spawnSync(venvPip, ['install', '--quiet', '-r', requirements], { stdio: 'inherit', cwd: root })
if (pipResult.status !== 0) {
  log('primer3-py-Installation fehlgeschlagen (z.B. fehlender C-Compiler) — Biologik nutzt bis auf Weiteres die Wallace-Tm-Schaetzung. Das ist unproblematisch, aber weniger genau.')
  process.exit(0)
}

log('Fertig — primer3-py ist in .venv installiert und wird automatisch von Biologik gefunden.')
