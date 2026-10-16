// Offline smoke tests of the classic GitLab selector + the 24-design Builder Filter.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const root=path.resolve(__dirname,'..','encapsulin_selector');
const read=f=>fs.readFileSync(path.join(root,f),'utf8');
const init=()=>{
 const events={}; const elements={};
 function el(id){return elements[id]??= {id,value:'',checked:id==='includeUnknown',textContent:'',innerHTML:'',dataset:{},listeners:{},style:{},
  classList:{toggle(){},add(){},remove(){}},addEventListener(n,cb){this.listeners[n]=cb},appendChild(){}};}
 const tabs=[el('search-tab'),el('finder-tab')]; tabs.forEach((t,i)=>{t.dataset.mode=i?'finder':'search'; t.classList.toggle=(_,val)=>{t.active=val};});tabs[0].active=true;
 const document={getElementById:el, querySelectorAll:x=>x==='.mode-tab'?tabs:[],
  querySelector:x=>x==='.mode-tab.active'?tabs.find(t=>t.active):x.startsWith('.mode-tab[data-mode=')?tabs.find(t=>t.dataset.mode===(x.match(/"([^"]+)"/)||[])[1]):null,
  createElement:()=>({value:'',textContent:''}), addEventListener(n,cb){events[n]=cb},
  documentElement:{getAttribute(){return 'light'},setAttribute(){}}};
 const values={};const storage={getItem:key=>values[key]||null,setItem:(k,v)=>values[k]=v};
 const window={addEventListener(){},location:{hash:''},scrollY:0,scrollTo(){}};
 const context={window,document,sessionStorage:storage,localStorage:storage,
  location:{href:'',hash:''},history:{replaceState(){},scrollRestoration:'auto'},console,alert:()=>{throw Error('unexpected alert')}};
 vm.createContext(context);vm.runInContext(read('selector-data.js'),context);vm.runInContext(read('builder-catalog.js'),context);
 return {context,el,tabs,storage,events};
};
const f=init();
vm.runInContext(read('builder-filter.js'),f.context);
assert.equal((f.el('designResults').innerHTML.match(/data-design-id=/g)||[]).length,24,'24 initial Builder designs');
const filterHtml=read('builder-filter.html');
assert(filterHtml.includes('class="finder-grid builder-finder-grid"'));
assert(filterHtml.indexOf('class="filter-panel builder-filter-panel"')<filterHtml.indexOf('id="designResults"'));
f.el('designType').value='engineered';f.el('designType').listeners.input();
assert(f.el('designResults').innerHTML.includes('Engineered'));
assert(!f.el('designResults').innerHTML.includes('<span class="chip wt">Wild Type</span>'));
f.el('resetBuilderFilters').listeners.click();
assert.equal((f.el('designResults').innerHTML.match(/data-design-id=/g)||[]).length,24,'Reset keeps all 24');
const transferId=f.context.window.ENCORE_BUILDER_CATALOG.find(d=>d.name.includes('Letter11')).sequence_id;
assert(transferId);
const design=f.context.window.ENCORE_BUILDER_CATALOG.find(d=>d.sequence_id===transferId);
f.events.click({target:{closest(){return {dataset:{designId:transferId}}}}});
const handoff=JSON.parse(f.storage.getItem('encore.selector.handoff'));
assert.equal(handoff.seq,design.cds,'Builder receives exact approved CDS');
assert.equal(handoff.design_id,transferId);
assert.equal(f.context.location.href,'/#step-1');
const e=init();
vm.runInContext(read('selector-alpha.js'),e.context);
function search(text){e.el('globalSearch').value=text;e.el('globalSearch').listeners.input();return e.el('searchResults').innerHTML;}
let html=search('Q1D6H4');
assert(html.includes('Reference position: 199–201 aa'), '3×His positions');
assert(html.includes('class="change-before">KTG</code>')&&html.includes('class="change-after">HHH</code>'),'Old/new residues');
assert(html.includes('Reference position: 196–203 aa'), 'Mx pmut positions');
html=search('Q9WZP2');
assert(html.includes('Reference position: 187 aa'),'Thermotoga mutation residue position');
html=search('A0A0F5HPP7');
assert(html.includes('Reference position: 193–209 aa'),'Letter11 loop');
html=search('I6WZG6');
assert(html.includes('Exact changed amino-acid sequence not verified'),'Incomplete His tag not fabricated');
console.log('PASS: 24 sequences, left Builder sidebar, filters, direct Builder CDS transfer, 4 scientific mutation comparisons.');
