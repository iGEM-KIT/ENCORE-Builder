import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import vm from 'node:vm'
import test from 'node:test'
import assert from 'node:assert/strict'
const root = resolve(import.meta.dirname, '../../..')
const read = name => readFileSync(resolve(root, name),'utf8')
function setup(){
  const elements = new Map(); const docEvents = {};
  const get = id => {
    if (!elements.has(id)) elements.set(id,{value:'',textContent:'',innerHTML:'',addEventListener(){}})
    return elements.get(id)
  }
  const copied=[];
  const ctx={window:{},document:{getElementById:get,addEventListener:(type,fn)=>{docEvents[type]=fn},documentElement:{getAttribute:()=>null,setAttribute(){}}},
    navigator:{clipboard:{writeText: async txt => {copied.push(txt)}}},
    localStorage:{getItem(){return null},setItem(){}},sessionStorage:{setItem(){}},location:{href:''}}
  vm.createContext(ctx)
  for (const path of ['encapsulin_selector/selector-data.js','encapsulin_selector/builder-catalog.js','encapsulin_selector/builder-filter.js']) vm.runInContext(read(path),ctx)
  return {ctx,get,docEvents,copied};
}
test('24 eligible designs have actual assembly sources with DOI/PDB where available, exact collapsed CDS previews and explicit cargo context',()=>{
  const {ctx,get}=setup();const html=get('designResults').innerHTML;
  const designs=ctx.window.ENCORE_BUILDER_CATALOG;const full=ctx.window.ENCAPSULIN_SELECTOR_DATA;
  assert.equal(designs.length,24)
  assert.equal((html.match(/class="design-sources"/g)||[]).length,24)
  assert.equal((html.match(/class="details builder-cds-preview"/g)||[]).length,24)
  assert.equal((html.match(/class="chip shell-only"/g)||[]).length,24)
  assert.equal((html.match(/class="chip cargo-free"/g)||[]).length,21)
  assert.equal((html.match(/class="chip cargo-unverified"/g)||[]).length,3)
  for(const d of designs){
    const a=full.assemblies.find(x=>x.assembly_id===d.assembly_id)
    assert(a, `Missing assembly ${d.assembly_id}`)
    assert(html.includes(`data-copy-seq="${d.sequence_id}"`), `Missing copy action ${d.sequence_id}`)
    assert(html.includes(d.cds.slice(0,60)), `The preview does not contain exact CDS for ${d.sequence_id}`)
    for(const l of full.citation_links.filter(x=>x.table==='assemblies'&&x.record_id===a.assembly_id)){
      if(l.doi?.startsWith('10.')) assert(html.includes(`https://doi.org/${l.doi}`), `Missing actual DOI ${l.doi}`)
    }
  }
  assert(!html.includes('https://doi.org/undefined'))
  assert.match(html,/I3E3I1/);assert.match(html,/McIver 2024/)
  assert.match(html,/View transferred DNA sequence \(CDS · 5′→3′/)
  assert.match(read('encapsulin_selector/builder-filter.html'),/optional choices at the cargo site/)
})
test('copy action retrieves exactly the same curated CDS passed to Builder',async()=>{
  const {ctx,docEvents,copied}=setup();const d=ctx.window.ENCORE_BUILDER_CATALOG.find(x=>x.name.includes('Letter11'))
  const button={dataset:{copySeq:d.sequence_id},textContent:'Copy CDS'}
  docEvents.click({target:{closest:selector=>selector==='[data-copy-seq]'?button:null}})
  await Promise.resolve();await Promise.resolve();
  assert.equal(copied[0],d.cds)
  assert.equal(button.textContent,'Copied!')
})
