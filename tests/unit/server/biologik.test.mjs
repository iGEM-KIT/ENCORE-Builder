// Tests of server/utils/biologik.js: the bridge that runs the Python engine for every request.
// The real engine is started (Biologik/level0_design needs no Python packages), so this also proves that the
// Node side and the Python side agree on the JSON protocol.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { runBiologik } from '../../../server/utils/biologik.js'

const CARGO = 'ATGGCTAAAGGTGAAGAACTGTTCACCGGTGTTGTTCCAATCTTGGTTGAATTGGATGGTGATGTT'

test('libraries: the dropdown data comes back without the ok field', async () => {
  const result = await runBiologik('libraries')
  assert.equal('ok' in result, false)
  assert.ok(result.libraries.nanocompartments.length >= 3)
  assert.ok(result.libraries.ncsCombined.some((c) => c.id === 'ncs12'))
})

test('validate: a good sequence passes, a sequence that is not fusion ready is an answer, not a crash', async () => {
  const good = await runBiologik('validate', { cargoSeq: CARGO, kind: 'cargo' })
  assert.equal(good.validation.ok, true)
  const bad = await runBiologik('validate', { cargoSeq: 'ATGC', kind: 'cargo' })
  assert.equal(bad.validation.ok, false)
  assert.ok(bad.validation.errors.length > 0)
})

test('to_dna: an amino acid sequence is back-translated three bases per residue', async () => {
  const result = await runBiologik('to_dna', { sequences: ['MKFEMKF', CARGO] })
  assert.equal(result.dna[0].length, 21)
  assert.equal(result.dna[1], CARGO)
})

test('design: a complete design comes back with all three levels, and genbank:true adds the export', async () => {
  const { design } = await runBiologik('design', { nanocompartment: 'tmari', cargoSeq: CARGO, cargoLabel: 'X', genbank: true })
  assert.equal(design.nanocompartment.id, 'tmari')
  assert.ok(design.level0Constructs.length >= 10)
  assert.equal(design.level1Constructs.length, 3)
  assert.ok(design.level2Construct)
  assert.match(design.genbank, /^LOCUS/m)
})

test('design: an invalid request is rejected with status 400 and the message of the engine', async () => {
  await assert.rejects(
    () => runBiologik('design', { nanocompartment: 'doesnotexist', cargoSeq: CARGO }),
    (error) => error.status === 400 && /doesnotexist/.test(error.message),
  )
})

test('an unknown command is a 400 as well', async () => {
  await assert.rejects(
    () => runBiologik('nonsense'),
    (error) => error.status === 400 && /Unknown command/.test(error.message),
  )
})

test('design: optimizeToolkit reaches the engine, re-optimizes the toolKIT shell and removes its XbaI site', async () => {
  const off = await runBiologik('design', { nanocompartment: 'tmari', cargoSeq: CARGO, cargoLabel: 'X' })
  const on = await runBiologik('design', { nanocompartment: 'tmari', cargoSeq: CARGO, cargoLabel: 'X', optimizeToolkit: true })
  assert.equal(off.design.toolkitOptimization.enabled, false)
  assert.deepEqual(off.design.toolkitOptimization.parts, [])
  assert.equal(on.design.toolkitOptimization.enabled, true)
  const shell = on.design.level0Constructs.find((c) => c.module === 'nc_site' && c.slot === 3)
  assert.equal(shell.reoptimized, true)
  assert.equal(shell.registryUrl, null)
  assert.deepEqual(on.design.toolkitOptimization.sitesInInsert, [])
})
