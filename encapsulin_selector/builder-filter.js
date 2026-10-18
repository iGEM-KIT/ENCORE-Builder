// Simple builder-facing filter. The scientific explorer remains independent.
(function () {
  'use strict';
  const full = window.ENCAPSULIN_SELECTOR_DATA;
  const designs = window.ENCORE_BUILDER_CATALOG;
  if (!full || !Array.isArray(designs)) {
    document.getElementById('designResults').textContent = 'Catalog unavailable. Run node scripts/build-selector-data.mjs.';
    return;
  }
  const $ = id => document.getElementById(id);
  const escape = val => String(val ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const assemblies = new Map(full.assemblies.map(a => [a.assembly_id, a]));
  const candidates = new Map(full.candidates.map(c => [c.candidate_id, c]));
  const tpById = new Map((full.targeting_peptides || []).map(tp => [tp.tp_id, tp]));
  const tpLinksBySequence = new Map();
  (full.tp_assembly_links || []).forEach(link => {
    if (!link.sequence_id || !tpById.has(link.tp_id)) return;
    const matches = tpLinksBySequence.get(link.sequence_id) || [];
    matches.push(link);
    tpLinksBySequence.set(link.sequence_id, matches);
  });
  const tpOptions = d => (tpLinksBySequence.get(d.sequence_id) || [])
    .filter(link => link.assembly_id === d.assembly_id && link.candidate_id === d.candidate_id)
    .map(link => {
      const tp = tpById.get(link.tp_id);
      return {
        tp_id: tp.tp_id, tp_sequence_aa: tp.tp_sequence_aa,
        builder_dna_5to3: tp.builder_dna_5to3 || null,
        cargo_terminus: tp.cargo_terminus,
        builder_transfer_status: link.builder_transfer_status,
        pair_specific_evidence_status: link.pair_specific_evidence_status,
        cargo_protein: tp.cargo_protein || '', source_doi: tp.source_doi || ''
      };
    });
  const transferable = tp => ['TOOLKIT_EXACT_AA_DNA','AA_ONLY_REQUIRES_DESIGN_DNA'].includes(tp.builder_transfer_status);
  function tpDetails(d) {
    const options = tpOptions(d);
    if (!options.length) return '';
    const usable = options.filter(transferable).length;
    return `<details class="details"><summary>Targeting peptides · ${options.length} associated (${usable} Builder option${usable === 1 ? '' : 's'})</summary>
      <p class="modification-note">Associated with this shell system; exact loading performance is not assumed for engineered variants. No TP is inserted into the shell sequence.</p>
      ${options.map(tp => `<div class="property-grid">
        ${property('TP', tp.tp_id)}
        ${property('Amino acids', tp.tp_sequence_aa)}
        ${property('Position', tp.cargo_terminus)}
        ${property('Builder transfer', transferable(tp) ? 'Optional cargo-site part' : 'Reference only')}
        ${property('Pair evidence', String(tp.pair_specific_evidence_status || '').replaceAll('_',' '))}
      </div>`).join('')}
    </details>`;
  }
  // Cite only the selected assembly, never a different pore mutant or related construct.
  const assemblyCitations = new Map();
  (full.citation_links || []).forEach(link => {
    if (link.table !== 'assemblies' || !link.record_id) return;
    if (!assemblyCitations.has(link.record_id)) assemblyCitations.set(link.record_id, []);
    assemblyCitations.get(link.record_id).push(link);
  });
  const poreCounts = new Map();
  full.pores.forEach(p => { if(p.assembly_id) poreCounts.set(p.assembly_id,(poreCounts.get(p.assembly_id)||0)+1); });
  const extraArchitectures = {
    Q1D6H4_T3: ['Q1D6H4_T1'],
    Q1D6H4_3xHis_T1: ['Q1D6H4_3xHis_Tet'],
    A0A0F5HPP7_Letter11_T4: ['A0A0F5HPP7_Letter11_T3'],
  };
  const related = d => [d.assembly_id, ...(extraArchitectures[d.assembly_id] || [])]
    .map(id => assemblies.get(id)).filter(Boolean);
  const number = raw => {
    if (typeof raw === 'number' && Number.isFinite(raw)) return raw;
    if (typeof raw !== 'string') return null;
    const s = raw.trim().replace(/^~/,'').replace(',','.');
    if (!/^\d+(\.\d+)?$/.test(s)) return null;
    const n = Number(s); return Number.isFinite(n) ? n : null;
  };
  const show = value => value == null || value === '' ? 'Not reported' : escape(value);
  function tName(a) {
    return a.assembly_symmetry === 'tetrahedral' ? 'T=N/A · Tetrahedral'
      : a.T_number != null ? 'T=' + a.T_number : 'Not reported';
  }
  function diameter(a) {
    return a.shell_diameter_nm == null || a.shell_diameter_nm === ''
      ? 'Not reported' : String(a.shell_diameter_nm) + ' nm';
  }
  function property(name, value) {
    return `<div class="prop"><span class="k">${escape(name)}</span><span class="v">${show(value)}</span></div>`;
  }
  function sourceBlock(a) {
    const links = assemblyCitations.get(a.assembly_id) || [];
    const seen = new Set();
    const reported = links.filter(link => {
      const key = String(link.doi || '').toLowerCase().trim();
      if (!/^10\.\d{4,9}\/[^\s<>'"]+$/i.test(key) || seen.has(key)) return false;
      seen.add(key); return true;
    }).map(link => `<a class="ext-link" href="https://doi.org/${encodeURI(link.doi)}" target="_blank" rel="noopener noreferrer" title="DOI: ${escape(link.doi)}">${escape(link.citation_label || link.doi)}</a>`);
    // Legacy records without indexed citation links: keep the curated source label.
    const rawDois = String(a.source_doi || '').split(';').map(x => x.trim()).filter(Boolean);
    rawDois.forEach(doi => {
      if (seen.has(doi.toLowerCase()) || !/^10\.\d{4,9}\/[^\s<>'"]+$/i.test(doi)) return;
      seen.add(doi.toLowerCase());
      reported.push(`<a class="ext-link" href="https://doi.org/${encodeURI(doi)}" target="_blank" rel="noopener noreferrer">${escape(doi)}</a>`);
    });
    let citations = reported.join(' <span aria-hidden="true">·</span> ');
    if (!citations) citations = escape(a.source || 'Not reported');
    const pdbIds = String(a.structure_id || '').split(';').map(id => id.trim()).filter(id => /^[0-9][a-z0-9]{3}$/i.test(id));
    const pdb = pdbIds.length ? ` <span class="design-pdb">PDB: ${pdbIds.map(id => `<a class="ext-link" href="https://www.rcsb.org/structure/${encodeURIComponent(id)}" target="_blank" rel="noopener noreferrer">${escape(id)}</a>`).join(', ')}</span>` : '';
    return `<div class="design-sources"><strong>Source:</strong> ${citations}${pdb}</div>`;
  }
  function cargoFreeReported(a) {
    // A shell-only Builder CDS is not in itself evidence that the published
    // experimental preparation lacked cargo protein.
    return /cargo[-\s]?free|\bempty\b|\bapo\b|nonloaded|without cargo|absence of cargo/i.test(String(a.condition || ''));
  }
  function sequencePreview(d) {
    if (typeof d.cds !== 'string' || !/^[ACGT]+$/.test(d.cds) || d.cds.length !== d.cds_length_nt) return '';
    const lines = d.cds.match(/.{1,60}/g).map(line => escape(line)).join('\n');
    return `<details class="details builder-cds-preview"><summary>View transferred DNA sequence (CDS · 5′→3′ · ${d.cds_length_nt} nt)</summary>
      <div class="builder-cds-body"><p>This is the <strong>exact approved shell CDS</strong> sent to the Builder. It includes no cargo or targeting peptide sequence.</p>
      <div class="builder-cds-heading"><span>DNA sequence (5′→3′)</span><button type="button" class="builder-copy-sequence" data-copy-seq="${escape(d.sequence_id)}" aria-label="Copy DNA sequence for ${escape(d.name)}">Copy CDS</button></div>
      <pre class="builder-cds-sequence">${lines}</pre></div>
    </details>`;
  }
  function card(d) {
    const a = assemblies.get(d.assembly_id);
    if (!a) return '';
    const other = related(d).filter(x => x.assembly_id !== d.assembly_id);
    const family = candidates.get(d.candidate_id)?.encapsulin_family;
    const countPores = poreCounts.get(a.assembly_id)||0;
    const engineered = a.shell_sequence_status === 'modified';
    const label = engineered ? 'Engineered' : 'Wild Type';
    return `<article class="assembly-card design-card">
      <div class="design-card-top">
        <div>
          <h3>${escape(d.name)}</h3>
          <p class="source"><i>${escape(d.organism)}</i> · ${escape(d.candidate_id)}</p>
          <div class="chips">
            <span class="chip ${engineered ? 'eng' : 'wt'}">${label}</span>
            <span class="chip ref">${escape(tName(a))}</span>
            <span class="chip">${escape(d.protein_length_aa)} aa</span>
            ${cargoFreeReported(a) ? '<span class="chip cargo-free">Cargo-free assembly</span>' : ''}
          </div>
        </div>
        <button class="use-nc" type="button" data-design-id="${escape(d.sequence_id)}">Select for Builder →</button>
      </div>
      <div class="property-grid">
        ${property('Shell diameter', diameter(a))}
        ${property('Subunits', a.shell_subunit_count)}
        ${property('CDS length', d.cds_length_nt + ' nt')}
      </div>
      ${engineered && a.shell_sequence_change ? `<p class="modification-note"><strong>Modification:</strong> ${escape(a.shell_sequence_change)}</p>` : ''}
      ${tpDetails(d)}
      ${sequencePreview(d)}
    </article>`;
  }
  function fitsDiameter(a, min, max) {
    if (min === '' && max === '') return true;
    const diameterValue = number(a.shell_diameter_nm);
    if (diameterValue == null) return false; // Unknown is not a measured match.
    return (min === '' || diameterValue >= +min) && (max === '' || diameterValue <= +max);
  }
  function filtered() {
    const query = $('designSearch').value.trim().toLowerCase();
    const typ = $('designType').value;
    const family = $('designFamily').value;
    const poreChoice = $('designPores').value;
    const t = $('designT').value;
    const min = $('designMin').value, max = $('designMax').value;
    if ((min !== '' && +min < 0) || (max !== '' && +max < 0) || (min !== '' && max !== '' && +min > +max)) {
      $('designSummary').textContent = 'Check your diameter range (min must not exceed max).';
      $('designResults').innerHTML = '';
      return;
    }
    const subset = designs.filter(d => {
      const a = assemblies.get(d.assembly_id);
      if (!a || d.translation_qc !== 'PASS') return false;
      if (query && ![d.name,d.organism,d.candidate_id,d.assembly_id,d.sequence_id]
        .some(x => String(x || '').toLowerCase().includes(query))) return false;
      if (typ && (a.shell_sequence_status === 'modified' ? 'engineered' : 'wild_type') !== typ) return false;
      if (family && candidates.get(d.candidate_id)?.encapsulin_family !== family) return false;
      if (poreChoice && !(poreChoice === 'yes' ? related(d).some(r => poreCounts.has(r.assembly_id)) : !related(d).some(r => poreCounts.has(r.assembly_id)))) return false;
      return related(d).some(r => {
        if (t && !(t === 'NA' ? r.assembly_symmetry === 'tetrahedral' : String(r.T_number) === t)) return false;
        return fitsDiameter(r,min,max);
      });
    });
    $('designSummary').textContent = `${subset.length} of ${designs.length} approved shell sequences`;
    $('designResults').innerHTML = subset.length ? subset.map(card).join('') :
      '<div class="empty-state">No approved shell sequence matches these requirements.</div>';
  }
  ['designSearch','designType','designFamily','designPores','designT','designMin','designMax']
    .forEach(id => $(id).addEventListener('input', filtered));
  $('resetBuilderFilters').addEventListener('click', () => {
    ['designSearch', 'designMin', 'designMax'].forEach(id => { $(id).value = ''; });
    ['designType', 'designFamily', 'designT', 'designPores'].forEach(id => { $(id).value = ''; });
    filtered();
  });
  document.addEventListener('click', ev => {
    const copyBtn = ev.target.closest('[data-copy-seq]');
    if (copyBtn && copyBtn.dataset.copySeq) {
      const found = designs.find(item => item.sequence_id === copyBtn.dataset.copySeq);
      if (!found || !/^[ACGT]+$/.test(found.cds) || found.cds.length !== found.cds_length_nt) return;
      if (!navigator.clipboard?.writeText) { copyBtn.textContent = 'Copy not available'; return; }
      navigator.clipboard.writeText(found.cds).then(() => {
        copyBtn.textContent = 'Copied!';
      }).catch(() => { copyBtn.textContent = 'Copy failed'; });
      return;
    }
    const btn = ev.target.closest('[data-design-id]');
    if (!btn) return;
    const d = designs.find(item => item.sequence_id === btn.dataset.designId);
    if (!d || d.translation_qc !== 'PASS' || !/^[ACGT]+$/.test(d.cds) || d.cds.length !== d.cds_length_nt) return;
    try {
      sessionStorage.setItem('encore.selector.handoff', JSON.stringify({
        label: `${d.name} · ${d.candidate_id}`.slice(0, 60),
        seq: d.cds, candidate_id: d.candidate_id, assembly_id: d.assembly_id,
        design_id: d.sequence_id, tp_options: tpOptions(d)
      }));
    } catch (error) {
      alert('Browser storage is unavailable. Cannot transfer the sequence in this tab.');
      return;
    }
    location.href = '/#step-1';
  });
  $('countBadge').textContent = `${designs.length} approved shell sequences`;
  filtered();
})();

// Keep original site-wide light/dark theme behavior.
(function initTheme() {
  const SUN = '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M5 19l1.5-1.5M17.5 6.5L19 5"/>';
  const MOON = '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>';
  const root = document.documentElement;
  function sync() {
    const dark = root.getAttribute('data-theme') === 'dark';
    document.getElementById('themeLabel').textContent = dark ? 'Dark' : 'Light';
    document.getElementById('themeIcon').innerHTML = dark ? MOON : SUN;
  }
  document.getElementById('themeToggle').addEventListener('click', () => {
    const dark = root.getAttribute('data-theme') !== 'dark';
    root.setAttribute('data-theme', dark ? 'dark' : 'light');
    try {localStorage.setItem('encore.theme', dark ? 'dark' : 'light')} catch(e) {}
    sync();
  });
  sync();
})();
