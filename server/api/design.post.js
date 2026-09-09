/**
 * POST /api/design
 * Body: {
 *   nanocompartment: string,   // decision 1 (id from /api/libraries)
 *   cargoSeq: string,          // decision 2 (raw CDS, no trailing stop codon)
 *   fusion: 'C' | 'N',         // decision 3
 *   cargoLabel?: string,
 *   linker?: string,           // linker id (default: first in library)
 *   promoter?: string,         // promoter id (default: GAL1-10)
 *   fasta?: boolean            // also return a FASTA export string
 * }
 *
 * Runs the Golden Gate design and returns the full assembly plan: 10 Level 0
 * parts (with Type overhangs), 2 Level 1 modules, the Level 2 construct,
 * cargo primers, the 96-well pick plan and the order list.
 */
import { spawn } from 'node:child_process'
import { resolve } from 'node:path'

const projectRoot = resolve(process.cwd())

async function designWithBiologik(decisions) {
  const python = process.env.BIOLOGIK_PYTHON || 'python3'
  const processResult = await new Promise((resolvePromise, reject) => {
    const child = spawn(python, ['-m', 'Biologik.level0_design.cli'], { cwd: projectRoot })
    let stdout = ''
    let stderr = ''
    child.stdout.on('data', (chunk) => { stdout += chunk })
    child.stderr.on('data', (chunk) => { stderr += chunk })
    child.on('error', reject)
    child.on('close', (code) => resolvePromise({ code, stdout, stderr }))
    child.stdin.end(JSON.stringify(decisions))
  })
  if (processResult.code !== 0) {
    const error = new Error(processResult.stderr || 'Biologik konnte das Design nicht erstellen.')
    error.status = 400
    throw error
  }
  const { stdout } = processResult
  const response = JSON.parse(stdout)
  if (!response.ok) {
    const error = new Error(response.error || 'Biologik konnte das Design nicht erstellen.')
    error.status = 400
    throw error
  }
  return response.design
}

export default defineEventHandler(async (event) => {
  const body = (await readBody(event)) || {}

  let design
  try {
    design = await designWithBiologik({
      nanocompartment: body.nanocompartment,
      cargoSeq: body.cargoSeq,
      cargoLabel: body.cargoLabel,
      fusion: body.fusion,
      linker: body.linker,
      promoter: body.promoter,
      fasta: Boolean(body.fasta),
    })
  } catch (err) {
    // The engine throws a plain Error with .status = 400 for invalid input.
    if (err?.status === 400) {
      throw createError({ statusCode: 400, statusMessage: err.message, data: err.data })
    }
    throw err
  }

  return design
})
