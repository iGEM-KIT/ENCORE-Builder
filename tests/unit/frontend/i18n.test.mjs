// The language engine (frontend/i18n.js) with the real dictionaries, run in Node with a minimal page stub.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

const root = new URL('../../../frontend/', import.meta.url)
const dict = code => JSON.parse(readFileSync(new URL(`i18n/${code}.json`, root), 'utf8'))

async function engine(code) {
  const store = {}
  const attrs = {}
  const ctx = {
    localStorage: { getItem: k => store[k] ?? null, setItem: (k, v) => { store[k] = v } },
    document: {
      readyState: 'complete', body: null, title: '',
      documentElement: { setAttribute: (k, v) => { attrs[k] = v }, getAttribute: k => attrs[k] },
      addEventListener() {},
    },
    fetch: async url => ({ ok: true, json: async () => dict(url.match(/\/i18n\/(\w+)\.json/)[1]) }),
    MutationObserver: class { observe() {} disconnect() {} },
    console,
  }
  ctx.window = ctx
  vm.createContext(ctx)
  vm.runInContext(readFileSync(new URL('i18n.js', root), 'utf8'), ctx)
  await ctx.ENCORE_I18N.setLang(code)
  return { api: ctx.ENCORE_I18N, attrs, store }
}

test('English is the default and nothing is translated', async () => {
  const { api, attrs } = await engine('en')
  assert.equal(api.lang, 'en')
  assert.equal(api.translate('Start builder'), null)
  assert.equal(attrs.lang, 'en')
})

test('the five languages are offered, English first', async () => {
  const { api } = await engine('en')
  assert.equal(JSON.stringify(api.languages.map(l => l.code)), JSON.stringify(['en', 'es', 'de', 'fr', 'zh']))
  assert.equal(api.languages.find(l => l.code === 'zh').name, '中文 (简体)')
})

test('an exact text is translated and the choice is kept and set on the page', async () => {
  const { api, attrs, store } = await engine('de')
  assert.equal(api.translate('Start builder'), 'Builder starten')
  assert.equal(api.translate('  Start   builder \n'), 'Builder starten')           // white space does not matter
  assert.equal(store['encore.lang'], 'de')
  assert.equal(attrs.lang, 'de')
})

test('a text with values is matched by its template and the values stay', async () => {
  const { api } = await engine('de')
  assert.equal(api.translate('Sequence too short (12 bp, need at least 30 bp).'), 'Sequenz zu kurz (12 bp, mindestens 30 bp nötig).')
  assert.equal(api.translate('Type 0.1 holds a sequence: a linker is required here.'), 'Typ 0.1 enthält eine Sequenz: Hier ist ein Linker nötig.')
})

test('a value that is itself a text is translated inside the template', async () => {
  const { api } = await engine('es')
  assert.equal(api.translate('SpyTag: 13 aa (not built)'), 'SpyTag: 13 aa (no construido)')      // the part name stays, the label is ours
  assert.equal(api.translate('NCS (spacer) (not built)'), 'NCS (espaciador) (no construido)')
})

test('a line made of pieces separated by a middle dot is translated piece by piece', async () => {
  const { api } = await engine('fr')
  assert.equal(api.translate('Type 0.3 · cargo site · toolbox part'), 'Type 0.3 · site du cargo · pièce du toolbox')
})

test('Mandarin is Simplified Chinese and the page language is set accordingly', async () => {
  const { api, attrs } = await engine('zh')
  assert.equal(api.translate('Start builder'), '启动 Builder')
  assert.equal(attrs.lang, 'zh-Hans')
})

test('the info windows come as whole pieces of HTML', async () => {
  const { api } = await engine('es')
  assert.match(api.html('info.stop.title', 'Start and stop codon'), /Codón de inicio y de parada/)
  assert.equal(api.html('info.unknown.title', 'English stays'), 'English stays')    // no entry: the English text
})

test('an unknown language falls back to English', async () => {
  const { api } = await engine('xx')
  assert.equal(api.lang, 'en')
})
