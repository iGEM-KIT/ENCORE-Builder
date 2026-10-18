import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const html = readFileSync('frontend/index.html','utf8');
const snippet=(from,to)=>{
  const i=html.indexOf(from); assert(i>=0,from);
  const j=html.indexOf(to,i); assert(j>i,to);
  return html.slice(i,j);
};
const seqC = {tp_id:'C_TP',tp_sequence_aa:'GGIWAFGS',cargo_terminus:'C_terminal',builder_dna_5to3:'GGAGGTATTTGGGCTTTCGGCTCT',builder_transfer_status:'TOOLKIT_EXACT_AA_DNA',pair_specific_evidence_status:'test_not_tested'};
const seqN = {tp_id:'N_TP',tp_sequence_aa:'LTVGSLRR',cargo_terminus:'N_terminal',builder_dna_5to3:null,builder_transfer_status:'AA_ONLY_REQUIRES_DESIGN_DNA',pair_specific_evidence_status:'literature_supported'};
const ref = {tp_id:'REF',tp_sequence_aa:'GGIWAFGS',cargo_terminus:'C_terminal',builder_dna_5to3:null,builder_transfer_status:'REFERENCE_ONLY_NOT_AUTODESIGN'};
const options=[seqC,seqN,ref];
function run(code, context){ vm.runInNewContext(code,context); }
const slotOptionsSource=snippet('function slotOptionsHtml(mod, n){','function slotCardHtml(mod,n){');
const slotFromSource=snippet('function setSlotFromSelect(mod,n){','function handleSlotSeq(mod,n){');
const availableAt=(item,mod,n)=>!item.slots || (item.slots[mod]||[]).includes(n);
const statusHint=()=>'';
function slotContext(){
  const ncs=[1,2,4,5].reduce((o,n)=>(o[n]={kind:'ncs'},o),{});
  const sl={cargo:ncs,nc:JSON.parse(JSON.stringify(ncs))};
  const el=n=>{
    const controls={'.slotsel':{value:'none'},'.slotcustom':{style:{}},'.slotlabel':{value:''},'.slotseq':{value:''}};
    return {controls,querySelector(sel){assert(sel in controls);return controls[sel];}};
  };
  const elements={1:el(1),5:el(5)};
  const ctx={LIB:{ncsCombined:[],linkers:[],surfaceMarkers:[],ncsStatus:{},targetingPeptides:[]},
    databaseTpOptions:options,canAutoDesignTp:t=>['TOOLKIT_EXACT_AA_DNA','AA_ONLY_REQUIRES_DESIGN_DNA'].includes(t.builder_transfer_status),
    availableAt, statusHint, ncsRoles:()=>['plain'],
    COMBINED:{}, slotEl:(mod,n)=>elements[n], slotsOf:mod=>sl[mod],
    databaseTpForCurrentShell:()=>true, enforceSlotRules:()=>{},updateConstructStrip:()=>{},refreshNav:()=>{},
    handleSlotSeq:(mod,n)=>{ sl[mod][n].valid=true; }, otherOfPair:()=>{}, setSlotSelect:()=>{}
  };
  return {ctx,sl,elements};
}

test('no duplicated TP input field remains',()=>{
  assert(!html.includes('id="importedTpSelect"'));
  assert(!html.includes('id="importedTpChoice"'));
  assert(html.includes('dbtp:'));
});
test('eligible database TPs appear in both existing cargo slots, with documented-placement labels',()=>{
  const {ctx}=slotContext();run(slotOptionsSource+'\nthis.slotOptionsHtml=slotOptionsHtml;',ctx);
  const cargo1=ctx.slotOptionsHtml('cargo',1),cargo5=ctx.slotOptionsHtml('cargo',5);
  for (const markup of [cargo1,cargo5]) {
    assert(markup.includes('dbtp:C_TP'));
    assert(markup.includes('dbtp:N_TP'));
    assert(!markup.includes('dbtp:REF'));
  }
  assert.match(cargo1,/C_TP[^<]*reported C-terminal/);
  assert.match(cargo1,/N_TP[^<]*alternative position \(not validated\)/);
  assert.match(cargo5,/N_TP[^<]*reported N-terminal/);
  assert.match(cargo5,/C_TP[^<]*alternative position \(not validated\)/);
  assert(!ctx.slotOptionsHtml('nc',1).includes('dbtp:'));
  assert(!ctx.slotOptionsHtml('cargo',2).includes('dbtp:'));
});
test('choosing database TP in Type 0.1 fills the existing cargo slot without second field',()=>{
  const {ctx,sl,elements}=slotContext();
  elements[1].controls['.slotsel'].value='dbtp:C_TP';
  run(slotFromSource+'\nthis.setSlotFromSelect=setSlotFromSelect;',ctx);
  ctx.setSlotFromSelect('cargo',1);
  assert.equal(sl.cargo[1].kind,'custom');
  assert.equal(sl.cargo[1].databaseTpId,seqC.tp_id);
  assert.equal(sl.cargo[1].seqRaw,seqC.builder_dna_5to3);
  assert.equal(elements[1].controls['.slotsel'].value,'dbtp:C_TP');
  assert.equal(elements[1].controls['.slotcustom'].style.display,'flex');
});
test('Type 0.5 accepts AA-only TP at reported N-terminus and Type 0.1 as an alternative',()=>{
  const {ctx,sl,elements}=slotContext();
  elements[5].controls['.slotsel'].value='dbtp:N_TP';
  run(slotFromSource+'\nthis.setSlotFromSelect=setSlotFromSelect;',ctx);
  ctx.setSlotFromSelect('cargo',5);
  assert.equal(sl.cargo[5].seqRaw,seqN.tp_sequence_aa);
  elements[1].controls['.slotsel'].value='dbtp:N_TP';
  ctx.setSlotFromSelect('cargo',1);
  assert.equal(sl.cargo[1].kind,'custom');
  assert.equal(sl.cargo[1].seqRaw,seqN.tp_sequence_aa);
  assert.equal(sl.cargo[1].databaseTpId,seqN.tp_id);
});

test('C-terminal TP can be inserted at N-terminal with warning and unchanged curated sequence',()=>{
  const {ctx,sl,elements}=slotContext();
  elements[5].controls['.slotsel'].value='dbtp:C_TP';
  run(slotFromSource+'\nthis.setSlotFromSelect=setSlotFromSelect;',ctx);
  ctx.setSlotFromSelect('cargo',5);
  assert.equal(sl.cargo[5].kind,'custom');
  assert.equal(sl.cargo[5].databaseTpId,seqC.tp_id);
  assert.equal(sl.cargo[5].seqRaw,seqC.builder_dna_5to3);
});

test('reference-only motif remains unavailable even if a slot is selected programmatically',()=>{
  const {ctx,sl,elements}=slotContext();
  elements[5].controls['.slotsel'].value='dbtp:REF';
  run(slotFromSource+'\nthis.setSlotFromSelect=setSlotFromSelect;',ctx);
  ctx.setSlotFromSelect('cargo',5);
  assert.equal(sl.cargo[5].kind,'ncs');
});

test('database TP choices remain selectable for the exact imported shell while validation is pending',()=>{
  const source=snippet('const importedShellVariants = raw =>','function applySelectorHandoff(){');
  const ctx={importedShellSeq:'ATGAAACCC',state:{nc:null,customNc:{seqRaw:'ATGAAACCC',valid:false}},CUSTOM_NC:'custom',
    $:()=>({value:'custom'}),clean:s=>s,endsWithStop:s=>['TAA','TAG','TGA'].includes(s.slice(-3))?s.slice(-3):null};
  run(source+'\nthis.gate=databaseTpForCurrentShell;',ctx);
  assert.equal(ctx.gate(),true,'a not-yet-validated shell must not disable TP options');
  ctx.state.customNc.seqRaw='ATGAAATTT';
  assert.equal(ctx.gate(),false,'a changed shell invalidates the imported TP context');
  ctx.state.customNc.seqRaw='ATGAAACCC';ctx.$=()=>({value:'toolkit'});
  assert.equal(ctx.gate(),false,'switching to a toolkit shell must invalidate the imported context');
  ctx.$=()=>({value:'custom'});ctx.importedShellSeq='';
  assert.equal(ctx.gate(),false,'never enable a database TP without a filter handoff');
});

test('disabled-state rules do not grey out imported TPs while shell validation is pending',()=>{
  const gate=snippet('const importedShellVariants = raw =>','function applySelectorHandoff(){');
  const enforce=snippet('function enforceSlotRules(mod){','function refreshNext0(){');
  const shell='ATGAAACCC';
  const slots={1:{kind:'ncs'},2:{kind:'ncs'},4:{kind:'ncs'},5:{kind:'ncs'}};
  const elements={};
  for(const n of [1,2,4,5]) {
    const options=['none','ncs','tp','dbtp:C_TP','dbtp:N_TP'].map(value=>({value,disabled:false}));
    const sel={disabled:false,options};
    const hint={textContent:'',style:{}};
    elements[n]={sel,hint,classList:{toggle(){}}};
  }
  const ctx={importedShellSeq:shell,CUSTOM_NC:'custom',state:{nc:null,customNc:{seqRaw:shell,valid:false}},
    $:()=>({value:'custom'}),clean:s=>s,endsWithStop:s=>['TAA','TAG','TGA'].includes(s.slice(-3))?s.slice(-3):null,slotsOf:()=>slots,SLOT_NUMBERS:[1,2,4,5],
    slotEl:(_mod,n)=>({querySelector:css=>css==='.slotsel'?elements[n].sel:elements[n].hint,classList:elements[n].classList}),
    LINKER_FOR:{2:1,4:5},COMBINED:{},blocksNcs:()=>false,needsLinker:()=>false,
    isTpPart:c=>c.kind==='tp'||!!c.databaseTpId,
    databaseTpOptions:options,canAutoDesignTp:t=>['TOOLKIT_EXACT_AA_DNA','AA_ONLY_REQUIRES_DESIGN_DNA'].includes(t.builder_transfer_status),
    firstLinker:()=>({kind:'linker',id:'a'}),handleSlotSeq:()=>{},updateConstructStrip:()=>{}};
  run(gate+'\n'+enforce+'\nthis.enforceSlotRules=enforceSlotRules;',ctx);
  ctx.enforceSlotRules('cargo');
  for(const n of [1,5]) assert.equal(elements[n].sel.options.find(o=>o.value==='dbtp:C_TP').disabled,false);
  slots[5]={kind:'tp'};
  ctx.enforceSlotRules('cargo');
  assert.equal(elements[1].sel.options.find(o=>o.value==='dbtp:C_TP').disabled,true,'a second TP is still prohibited');
  assert.match(elements[1].hint.textContent,/Another targeting peptide/);
});


test('removing the shell start and/or stop codon does not grey out its Database TPs',()=>{
  const gate=snippet('const importedShellVariants = raw =>','function applySelectorHandoff(){');
  const ref='ATGAAACCCGGGTAA';
  const state={customNc:{seqRaw:ref,valid:false}};
  const ctx={importedShellSeq:ref,state,CUSTOM_NC:'custom',$:()=>({value:'custom'}),clean:s=>s,
    endsWithStop:s=>['TAA','TAG','TGA'].includes(s.slice(-3))?s.slice(-3):null};
  run(gate+'\nthis.canSelect=databaseTpForCurrentShell;',ctx);
  for(const sequence of [ref,'AAACCCGGGTAA','ATGAAACCCGGG','AAACCCGGG']) {
    state.customNc.seqRaw=sequence;
    assert.equal(ctx.canSelect(),true,`expected terminal-codon variant ${sequence} to preserve TP selection`);
  }
  for(const sequence of ['AAACCCGGGA','ATGAAACCCGGGAAA','ATGAAACCCGGGTAG','TTGAAACCCGGGTAA','']){
    state.customNc.seqRaw=sequence;
    assert.equal(ctx.canSelect(),false,`edited shell ${sequence} must not retain TP associations`);
  }
  state.customNc.seqRaw='AAACCCGGG'; ctx.$=()=>({value:'toolkit'});
  assert.equal(ctx.canSelect(),false,'switching to a different shell should invalidate TP options');
});

test('enforceSlotRules keeps exact imported TP available after the strip button removes terminal codons',()=>{
  const gate=snippet('const importedShellVariants = raw =>','function applySelectorHandoff(){');
  const enforce=snippet('function enforceSlotRules(mod){','function refreshNext0(){');
  const shell='ATGAAACCCGGGTAA';
  const slots={1:{kind:'ncs'},2:{kind:'ncs'},4:{kind:'ncs'},5:{kind:'ncs'}};
  const elements={};
  for(const n of [1,2,4,5]){
    const options=['none','ncs','tp','dbtp:C_TP','dbtp:N_TP'].map(value=>({value,disabled:false}));
    const sel={disabled:false,options}, hint={textContent:'',style:{}};
    elements[n]={sel,hint,classList:{toggle(){}}};
  }
  const state={customNc:{seqRaw:shell,valid:true},nc:{custom:true,tp:null}};
  const ctx={importedShellSeq:shell,CUSTOM_NC:'custom',state,$:()=>({value:'custom'}),clean:s=>s,
    endsWithStop:s=>['TAA','TAG','TGA'].includes(s.slice(-3))?s.slice(-3):null,
    slotsOf:()=>slots,SLOT_NUMBERS:[1,2,4,5],
    slotEl:(_mod,n)=>({querySelector:css=>css==='.slotsel'?elements[n].sel:elements[n].hint,classList:elements[n].classList}),
    LINKER_FOR:{2:1,4:5},COMBINED:{},blocksNcs:()=>false,needsLinker:()=>false,
    isTpPart:c=>c.kind==='tp'||!!c.databaseTpId,
    databaseTpOptions:[seqC,seqN],canAutoDesignTp:t=>['TOOLKIT_EXACT_AA_DNA','AA_ONLY_REQUIRES_DESIGN_DNA'].includes(t.builder_transfer_status),
    firstLinker:()=>({kind:'linker',id:'a'}),handleSlotSeq:()=>{},updateConstructStrip:()=>{}};
  run(gate+'\n'+enforce+'\nthis.enforceSlotRules=enforceSlotRules;',ctx);
  state.customNc.seqRaw='AAACCCGGG'; // exactly what the Builder's strip button writes
  ctx.enforceSlotRules('cargo');
  for(const n of [1,5]) assert.equal(elements[n].sel.options.find(o=>o.value==='dbtp:C_TP').disabled,false);
  state.customNc.seqRaw='AAACCCGGA';
  ctx.enforceSlotRules('cargo');
  for(const n of [1,5]) assert.equal(elements[n].sel.options.find(o=>o.value==='dbtp:C_TP').disabled,true);
  state.customNc.seqRaw='AAACCCGGG';
  ctx.enforceSlotRules('cargo');
  for(const n of [1,5]) assert.equal(elements[n].sel.options.find(o=>o.value==='dbtp:C_TP').disabled,false);
});
