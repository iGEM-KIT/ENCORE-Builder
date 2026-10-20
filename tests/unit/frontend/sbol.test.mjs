// The GenBank to SBOL 3 converter (frontend/sbol.js), run in Node with a minimal stub of the browser window.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

const ctx = {}
ctx.window = ctx
vm.createContext(ctx)
vm.runInContext(readFileSync(new URL('../../../frontend/sbol.js', import.meta.url), 'utf8'), ctx)
const sbol = ctx.ENCORE_SBOL

const RECORD = name => `LOCUS       ${name}      24 bp    DNA     circular   SYN
DEFINITION  A test record
            with a second line.
FEATURES             Location/Qualifiers
     promoter        1..6
                     /label="P1"
     CDS             complement(7..12)
                     /label="Gene <i>x</i>"
                     /note="first line
                     second line"
     misc_feature    join(13..15,19..21)
                     /label="BbsI"
     misc_feature    24
                     /label="one base"
ORIGIN
        1 acgtac gtacgt acgtac gtac
//
`

test('a record becomes a Component with its Sequence and one SequenceFeature per GenBank feature', () => {
  const ttl = sbol.fromGenbank(RECORD('rec-1'))
  assert.match(ttl, /a sbol:Component/)
  assert.match(ttl, /sbol:displayId "rec_1"/)                         // a hyphen is not allowed in a displayId
  assert.match(ttl, /sbol:elements "acgtacgtacgtacgtacgtac"/)
  assert.equal((ttl.match(/a sbol:SequenceFeature/g) || []).length, 4)
  assert.match(ttl, /SO:0000988/)                                      // circular
  assert.match(ttl, /sbol:description "A test record with a second line\."/)
})

test('locations keep their positions and strand, a join gives two ranges, markup is removed from names', () => {
  const ttl = sbol.fromGenbank(RECORD('r'))
  const ranges = [...ttl.matchAll(/sbol:start (\d+) ;\n\s+sbol:end (\d+) ;\n\s+sbol:orientation <https:\/\/identifiers.org\/SO:(\d+)>/g)].map(m => m.slice(1, 4).join(','))
  assert.deepEqual(ranges, ['1,6,0001030', '7,12,0001031', '13,15,0001030', '19,21,0001030', '24,24,0001030'])
  assert.match(ttl, /sbol:name "Gene x"/)
  assert.match(ttl, /sbol:description "first line second line"/)
  assert.match(ttl, /sbol:role <https:\/\/identifiers.org\/SO:0001687>/)   // BbsI is a restriction site
})

test('several records give several Components with different ids, also when the names repeat', () => {
  const ttl = sbol.fromGenbank(RECORD('same') + RECORD('same') + RECORD('1st'))
  assert.equal((ttl.match(/a sbol:Component/g) || []).length, 3)
  assert.match(ttl, /sbol:displayId "same_2"/)
  assert.match(ttl, /sbol:displayId "n1st"/)                           // a displayId starts with a letter
})

test('text that is no GenBank record gives a document without components', () => {
  assert.equal((sbol.fromGenbank('hello') .match(/a sbol:Component/g) || []).length, 0)
})
