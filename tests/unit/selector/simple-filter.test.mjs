import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import vm from 'node:vm'
import test from 'node:test'
import assert from 'node:assert/strict'
const root=resolve(import.meta.dirname, '../../..')
const read=path=>readFileSync(resolve(root,path),'utf8')
function setup(){
 const dom=new Map(); const listeners={};const documentListeners={};const storage=new Map();
 const get=id=>{
  if (!dom.has(id)) dom.set(id,{ value:'', checked:false, innerHTML:'',textContent:'',addEventListener:(ev,fn)=>{(listeners[id]??={})[ev]=fn} });
  return dom.get(id)
 };
 const context={
  window:{},
  document:{ getElementById:get, addEventListener:(ev,fn)=>{documentListeners[ev]=fn}, documentElement:{getAttribute:()=>null,setAttribute:()=>{}} },
  sessionStorage:{setItem:(k,v)=>storage.set(k,v),getItem:k=>storage.get(k)},
  localStorage:{setItem:()=>{}},
  location:{href:'http://localhost:8080/selector/builder-filter.html'},
  alert:(message)=>{throw Error(message)},
 };
 vm.createContext(context)
 for (const file of ['encapsulin_selector/selector-data.js','encapsulin_selector/builder-catalog.js','encapsulin_selector/builder-filter.js']) vm.runInContext(read(file),context)
 const render=()=>documentListeners;const trigger=id=>(listeners[id]?.input?.());
 return {context,get,trigger,storage,documentListeners}
}
test('exactly 24 CDS designs from original UI + reviewed catalog',()=>{
 const {context,get}=setup();
 assert.equal(context.window.ENCORE_BUILDER_CATALOG.length,24)
 assert.match(get('designSummary').textContent,/24 of 24/)
 assert.equal((get('designResults').innerHTML.match(/class="assembly-card design-card"/g)||[]).length,24)
 assert.match(get('designResults').innerHTML,/class="chip wt"/)
 assert.match(get('designResults').innerHTML,/class="chip eng"/)
})
test('Letter11 remains discoverable by T=3 or T=4 without duplicate CDS',()=>{
 const {get,trigger}=setup();
 get('designSearch').value='Letter11';trigger('designSearch');
 assert.match(get('designSummary').textContent,/1 of 24/)
 for(const t of ['3','4']){get('designT').value=t;trigger('designT');assert.match(get('designSummary').textContent,/1 of 24/)}
 get('designT').value='1';trigger('designT');assert.match(get('designSummary').textContent,/0 of 24/)
})
test('tetrahedral 3×His documented without invented T-number or diameter',()=>{
 const {get,trigger}=setup();get('designSearch').value='3×His';trigger('designSearch');
 get('designT').value='NA';trigger('designT');assert.match(get('designSummary').textContent,/1 of 24/)
 assert.match(get('designResults').innerHTML,/T=N\/A · Tetrahedral/)
})
test('numeric filters do not treat missing diameter as zero; min > max blocked',()=>{
 const {get,trigger}=setup();get('designMin').value='100';trigger('designMin');assert.match(get('designSummary').textContent,/0 of 24/)
 get('designMin').value='30';get('designMax').value='20';trigger('designMax');assert.match(get('designSummary').textContent,/Check your diameter range/)
})
test('one-click Builder transfer carries the exact curated CDS and NO scientific warning',()=>{
 const {context,get,trigger,storage,documentListeners}=setup();
 const d=context.window.ENCORE_BUILDER_CATALOG.find(x=>x.name.includes('Letter11'));
 documentListeners.click({target:{closest:()=>({dataset:{designId:d.sequence_id}})}})
 const h=JSON.parse(storage.get('encore.selector.handoff'))
 assert.equal(h.seq,d.cds);assert.equal(h.seq.length,816);assert.equal(h.design_id,d.sequence_id)
 assert.equal(h.warning,undefined);assert.equal(context.location.href,'/#step-1')
 assert(h.tp_options.length>0)
 assert(h.tp_options.every(x=>typeof x.tp_id==='string' && typeof x.tp_sequence_aa==='string'))
})
test('every assembly has comparison status; original Explore does not transfer',()=>{
 const {context}=setup();
 const data=context.window.ENCAPSULIN_SELECTOR_DATA
 assert.equal(data.assemblies.length,51)
 assert(data.assemblies.every(a=>['modified','unmodified'].includes(a.shell_sequence_status)))
 assert(data.assemblies.filter(a=>a.shell_sequence_status==='modified').every(a=>a.shell_sequence_change))
 assert.equal(data.candidates.find(c=>c.candidate_id==='Q9WZP2').reference_assembly_id,'Q9WZP2_T1_empty')
 assert(!read('encapsulin_selector/selector-alpha.js').includes('[data-use-nc]'))
 assert(!read('encapsulin_selector/selector-alpha.html').includes('Select for Builder'))
})

test('TP associations are passed by exact assembly and reference-only motifs stay reference-only',()=>{
 const {context,storage,documentListeners}=setup();
 const d=context.window.ENCORE_BUILDER_CATALOG.find(x=>x.candidate_id==='Q9WZP2' && x.assembly_id==='Q9WZP2_S1K_T1');
 assert(d)
 documentListeners.click({target:{closest:()=>({dataset:{designId:d.sequence_id}})}})
 const h=JSON.parse(storage.get('encore.selector.handoff'));
 const options=h.tp_options;
 const table=context.window.ENCAPSULIN_SELECTOR_DATA.tp_assembly_links;
 assert.equal(options.length,table.filter(x=>x.sequence_id===d.sequence_id && x.assembly_id===d.assembly_id).length)
 assert(options.some(x=>x.builder_transfer_status==='TOOLKIT_EXACT_AA_DNA' && /^[ACGT]+$/.test(x.builder_dna_5to3)))
 assert(options.some(x=>x.builder_transfer_status==='REFERENCE_ONLY_NOT_AUTODESIGN'))
 assert(options.some(x=>x.pair_specific_evidence_status==='exact_engineered_variant_TP_loading_not_tested'))
})
