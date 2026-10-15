// Tests of server/utils/commec.js (the bridge to the biosecurity screening container).
// Run with: pnpm test:node (or: node --test tests/unit/server/biologik.test.mjs tests/unit/server/commec.test.mjs)
// fetch is replaced, so no container is needed. The point of the module is that a missing or broken screening
// never turns into an error for the design: it always answers {available: false, reason}.
import { test, beforeEach, afterEach, mock } from 'node:test'
import assert from 'node:assert/strict'
import { checkCommecHealth, screenSequences } from '../../../server/utils/commec.js'

const jsonResponse = (body, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })

let savedUrl, savedTimeout
beforeEach(() => {
  savedUrl = process.env.COMMEC_URL
  savedTimeout = process.env.COMMEC_TIMEOUT_MS
  process.env.COMMEC_URL = 'http://commec:8787/'
})
afterEach(() => {
  mock.restoreAll()
  if (savedUrl === undefined) delete process.env.COMMEC_URL
  else process.env.COMMEC_URL = savedUrl
  if (savedTimeout === undefined) delete process.env.COMMEC_TIMEOUT_MS
  else process.env.COMMEC_TIMEOUT_MS = savedTimeout
})

const SEQS = [{ label: 'cargo', sequence: 'ATGGCTAAAGGTGAAGAACTGTTCACC' }]

test('health: without COMMEC_URL the screening is simply off', async () => {
  delete process.env.COMMEC_URL
  const result = await checkCommecHealth()
  assert.equal(result.available, false)
  assert.match(result.reason, /COMMEC_URL is not set/)
})

test('health: ok when the sidecar reports ready databases, and the trailing slash of the URL is ignored', async () => {
  const fetchMock = mock.method(globalThis, 'fetch', async () => jsonResponse({ ok: true, detail: '/databases' }))
  assert.deepEqual(await checkCommecHealth(), { available: true })
  assert.equal(fetchMock.mock.calls[0].arguments[0], 'http://commec:8787/health')
})

test('health: not available while the databases are still downloading', async () => {
  mock.method(globalThis, 'fetch', async () => jsonResponse({ ok: false, detail: 'being downloaded' }))
  const result = await checkCommecHealth()
  assert.equal(result.available, false)
  assert.equal(result.reason, 'being downloaded')
})

test('health: a failing container or an unreachable host gives a reason instead of an exception', async () => {
  mock.method(globalThis, 'fetch', async () => jsonResponse({}, 503))
  assert.match((await checkCommecHealth()).reason, /responded 503/)
  mock.restoreAll()
  mock.method(globalThis, 'fetch', async () => { throw new TypeError('fetch failed') })
  const result = await checkCommecHealth()
  assert.equal(result.available, false)
  assert.match(result.reason, /Could not reach commec-service at http:\/\/commec:8787: fetch failed/)
})

test('screen: without COMMEC_URL the screening is disabled with an explanation', async () => {
  delete process.env.COMMEC_URL
  const result = await screenSequences(SEQS)
  assert.equal(result.available, false)
  assert.match(result.reason, /disabled/)
})

test('screen: no sequences need no request at all', async () => {
  const fetchMock = mock.method(globalThis, 'fetch', async () => jsonResponse({ results: [] }))
  assert.deepEqual(await screenSequences([]), { available: true, results: [] })
  assert.equal(fetchMock.mock.callCount(), 0)
})

test('screen: posts the sequences and returns the results in order', async () => {
  const results = [{ available: true, status: { screen_status: 'Pass', biorisk: 'Pass' } }]
  const fetchMock = mock.method(globalThis, 'fetch', async () => jsonResponse({ results }))
  const out = await screenSequences(SEQS)
  assert.deepEqual(out, { available: true, results })
  const [url, options] = fetchMock.mock.calls[0].arguments
  assert.equal(url, 'http://commec:8787/screen')
  assert.equal(options.method, 'POST')
  assert.deepEqual(JSON.parse(options.body), { sequences: SEQS })
})

test('screen: every failure becomes available:false with a reason', async () => {
  mock.method(globalThis, 'fetch', async () => new Response('boom', { status: 500 }))
  const serverError = await screenSequences(SEQS)
  assert.equal(serverError.available, false)
  assert.match(serverError.reason, /responded 500: boom/)

  mock.restoreAll()
  mock.method(globalThis, 'fetch', async () => jsonResponse({ unexpected: true }))
  assert.match((await screenSequences(SEQS)).reason, /unexpected shape/)

  mock.restoreAll()
  mock.method(globalThis, 'fetch', async () => { throw new TypeError('fetch failed') })
  assert.match((await screenSequences(SEQS)).reason, /Could not reach commec-service/)
})

test('screen: a service that does not answer in time is reported, not waited for forever', async () => {
  process.env.COMMEC_TIMEOUT_MS = '50'
  mock.method(globalThis, 'fetch', (url, options) => new Promise((resolve, reject) => {
    options.signal.addEventListener('abort', () => reject(Object.assign(new Error('aborted'), { name: 'AbortError' })))
  }))
  const result = await screenSequences(SEQS)
  assert.equal(result.available, false)
  assert.match(result.reason, /did not respond within/)
})
