(() => {
  const DATA = window.ENCAPSULIN_SELECTOR_DATA;
  const candidates = DATA.candidates;
  const assemblies = DATA.assemblies;
  const sequences = DATA.sequences ?? [];
  const pores = DATA.pores ?? [];
  const targetingPeptides = DATA.targeting_peptides ?? [];
  const tpAssemblyLinks = DATA.tp_assembly_links ?? [];
  const tpsByCandidate = new Map();
  for (const tp of targetingPeptides) {
    if (!tpsByCandidate.has(tp.candidate_id)) tpsByCandidate.set(tp.candidate_id, []);
    tpsByCandidate.get(tp.candidate_id).push(tp);
  }
  const tpLinksById = new Map();
  for (const link of tpAssemblyLinks) {
    if (!tpLinksById.has(link.tp_id)) tpLinksById.set(link.tp_id, []);
    tpLinksById.get(link.tp_id).push(link);
  }
  const doiById = new Map((DATA.doi_index ?? []).map(ref => [ref.doi.toLowerCase(), ref]));
  const citationsByRecord = new Map();
  (DATA.citation_links ?? []).forEach(link => {
    const key = `${link.table}:${link.record_id}`;
    if (!citationsByRecord.has(key)) citationsByRecord.set(key, []);
    citationsByRecord.get(key).push(link);
  });
  const poresByAssembly = new Map();
  pores.forEach(pore => {
    if (!pore.assembly_id) return; // Do not attribute a pore to an unrelated variant.
    if (!poresByAssembly.has(pore.assembly_id)) poresByAssembly.set(pore.assembly_id, []);
    poresByAssembly.get(pore.assembly_id).push(pore);
  });
  const byCandidate = new Map();
  assemblies.forEach(a => {
    if (!byCandidate.has(a.candidate_id)) byCandidate.set(a.candidate_id, []);
    byCandidate.get(a.candidate_id).push(a);
  });
  const sequencesByCandidate = new Map();

sequences.forEach(s => {
  if (!sequencesByCandidate.has(s.candidate_id)) {
    sequencesByCandidate.set(s.candidate_id, []);
  }
  sequencesByCandidate.get(s.candidate_id).push(s);
});
  const candidateMap = new Map(candidates.map(c => [c.candidate_id, c]));

  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"
  }[ch]));
  const norm = value => String(value ?? "")
    .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .toLowerCase().replace(/\s+/g, " ").trim();
  const display = value => (value === null || value === undefined || String(value).trim() === "")
    ? "not reported" : String(value);
  // Humanize controlled vocabulary values for display only. Never transform IDs,
  // accession numbers, sequences, links or the values used by the filter logic.
  const vocabularyLabels = {
    not_reported: "Not reported",
    wild_type: "Wild-type",
    single_state_observed: "Single state observed",
    reported_diameter: "Reported diameter",
    narrowest_point: "Narrowest point",
    measured_from_structure: "Measured from structure",
    partial_icosahedral: "Partial icosahedral",
    type_1: "Type 1",
    type_2: "Type 2"
  };
  function humanValue(value) {
    if (value === null || value === undefined || String(value).trim() === "") return "Not reported";
    const raw = String(value).trim();
    if (vocabularyLabels[raw]) return vocabularyLabels[raw];
    return raw.replace(/_/g, " ").replace(/^./, letter => letter.toUpperCase());
  }
  function enumProperty(label, value) {
    return property(label, humanValue(value));
  }
  function strandLabel(value) {
    return value === "+" ? "Positive (+)" : value === "-" ? "Negative (−)" : humanValue(value);
  }

  function readLocaleNumber(raw) {
    const s = String(raw ?? "").trim();
    if (!s) return {empty:true, valid:true, value:null};
    const normalized = s.replace(/\s/g, "").replace(",", ".");
    if (!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/.test(normalized)) {
      return {empty:false, valid:false, value:null};
    }
    const value = Number(normalized);
    return {empty:false, valid:Number.isFinite(value), value};
  }

  function validateFinderInputs() {
    const fields = [
      ["diameterMin", "Minimum diameter"],
      ["diameterMax", "Maximum diameter"],
      ["targetDiameter", "Preferred diameter"],
      ["poreDiameterMin", "Minimum pore diameter"],
      ["poreDiameterMax", "Maximum pore diameter"]
    ];
    const errors = [];
    for (const [id,label] of fields) {
      const p = readLocaleNumber($(id).value);
      if (!p.valid) errors.push(`${label}: use a number such as 0,1 or 0.1.`);
    }
    const min = readLocaleNumber($("diameterMin").value);
    const max = readLocaleNumber($("diameterMax").value);
    if (min.valid && max.valid && !min.empty && !max.empty && min.value > max.value) {
      errors.push("Minimum diameter cannot be greater than maximum diameter.");
    }
    const pmin = readLocaleNumber($("poreDiameterMin").value);
    const pmax = readLocaleNumber($("poreDiameterMax").value);
    if (pmin.valid && pmax.valid && !pmin.empty && !pmax.empty && pmin.value > pmax.value) {
      errors.push("Minimum pore diameter cannot be greater than maximum pore diameter.");
    }
    const box = $("filterError");
    if (box) {
      box.textContent = errors.join(" ");
      box.classList.toggle("hidden", errors.length === 0);
    }
    return errors.length === 0;
  }

  $("datasetBadge").textContent =
    `${candidates.length} candidates • ${assemblies.length} assemblies • ${pores.length} pore observations • ${targetingPeptides.length} TP records`;
  $("alphaNote").textContent =
    "Pore filters use recorded observations for a specific assembly, not an assumed property of every variant. " +
    "Missing pore measurements are kept as potential matches. " +
    "Sources link to the original scientific publications.";

  // Mode switching
  // Each tab gets its own history entry (#search / #finder) so the browser
  // back/forward arrows switch between them.
  function setMode(mode) {
    document.querySelectorAll(".mode-tab").forEach(x => x.classList.toggle("active", x.dataset.mode === mode));
    $("searchMode").classList.toggle("hidden", mode !== "search");
    $("finderMode").classList.toggle("hidden", mode !== "finder");
  }
  const modeFromHash = () => {
    const m = location.hash.slice(1);
    return document.querySelector(`.mode-tab[data-mode="${m}"]`) ? m : null;
  };
  document.querySelectorAll(".mode-tab").forEach(btn => {
    btn.addEventListener("click", () => {
      const mode = btn.dataset.mode;
      setMode(mode);
      if (location.hash !== "#" + mode) history.pushState(null, "", "#" + mode);
    });
  });
  window.addEventListener("popstate", () => setMode(modeFromHash() || "search"));

  const unique = field => [...new Set(assemblies.map(a => a[field]).filter(v => v !== null && v !== ""))]
    .sort((a,b) => String(a).localeCompare(String(b), undefined, {numeric:true}));

  unique("assembly_symmetry").forEach(v => {
    const o = document.createElement("option"); o.value=v; o.textContent=humanValue(v); $("symmetry").appendChild(o);
  });
  unique("shell_subunit_count").forEach(v => {
    const o = document.createElement("option"); o.value=v; o.textContent=v; $("subunitCount").appendChild(o);
  });
  [...new Set(pores.map(p => p.pore_type).filter(Boolean))]
    .sort().forEach(v => {
      const o = document.createElement("option");
      o.value = v;
      o.textContent = poreLabelsForSelect(v);
      $("poreType").appendChild(o);
    });
  function poreLabelsForSelect(value) {
    return ({"2fold":"2-fold", "3fold":"3-fold", "5fold":"5-fold",
      "2fold_adjacent":"2-fold adjacent", "5fold_adjacent":"5-fold adjacent",
      "pseudo_3fold_PHH":"Pseudo-3-fold (PHH)",
      "hexamer_center":"Hexamer center"})[value] || value;
  }

  function assemblyWhy(a) {
    const bits = [];
    if (a.shell_diameter_nm !== null) bits.push(`${a.shell_diameter_nm} nm shell`);
    if (a.T_number !== null) bits.push(`T=${a.T_number}`);
    bits.push(a.variant_status === "wild_type" ? "WT" : "engineered");
    if (a.shell_subunit_count !== null) bits.push(`${a.shell_subunit_count} subunits`);
    if (a.structure_id) bits.push("structure ID recorded");
    return bits.join(" • ");
  }

  function property(label, value) {
    return `<div class="prop"><span class="k">${esc(label)}</span><span class="v">${esc(display(value))}</span></div>`;
  }

  // structure_id can hold several semicolon-separated PDB codes (e.g. "4PT2; 7S20");   // link each to its RCSB PDB entry. Assemblies have no UniProt entry of their own
  // (UniProt indexes protein sequences, not individual experimental structures or
  // engineered variants), so the PDB structure is the correct per-variant reference.
  function propertyPdb(label, value) {
    if (!value) return property(label, value);
    const links = String(value).split(";").map(s => s.trim()).filter(Boolean)
      .map(id => `<a class="ext-link" href="https://www.rcsb.org/structure/${esc(id)}" target="_blank" rel="noopener">${esc(id)}</a>`)
      .join(", ");
    return `<div class="prop"><span class="k">${esc(label)}</span><span class="v">${links}</span></div>`;
  }

  function doiLink(doi, label = doi) {
    if (!doi || !/^10\.\d{4,9}\/[^\s<>"']+$/i.test(String(doi).trim())) return esc(display(label));
    const clean = String(doi).trim();
    return `<a class="ext-link" href="https://doi.org/${encodeURI(clean).replace(/%25/g, '%2525')}" target="_blank" rel="noopener noreferrer">${esc(label)}</a>`;
  }

  // These links are indexed by (table, record_id): a citation for one engineered
  // pore must never appear as evidence for a different assembly or pore.
  function citationBlock(table, recordId) {
    const linked = citationsByRecord.get(`${table}:${recordId}`) || [];
    if (!linked.length) return "";
    const rows = linked.map(link => {
      const ref = doiById.get(String(link.doi || "").toLowerCase());
      const title = ref?.article_title ? `: ${esc(ref.article_title)}` : "";
      const context = link.relationship ? ` <span class="citation-role">(${esc(link.relationship)})</span>` : "";
      return `<li>${doiLink(link.doi, ref?.citation_label || link.citation_label || link.doi)}${title}${context}</li>`;
    }).join("");
    return `<details class="details citations"><summary>Source (${linked.length})</summary><ul>${rows}</ul></details>`;
  }

  const poreLabels = {
    "2fold": "2-fold", "3fold": "3-fold", "5fold": "5-fold",
    "2fold_adjacent": "2-fold adjacent", "5fold_adjacent": "5-fold adjacent",
    "pseudo_3fold_PHH": "Pseudo-3-fold (PHH)", "hexamer_center": "Hexamer-center"
  };
  const poreLabel = value => poreLabels[value] || humanValue(value);
  const poreDiameter = p => typeof p.pore_diameter_nm === "number" && Number.isFinite(p.pore_diameter_nm)
    ? `${p.pore_diameter_nm} nm` : "Not reported";

  // Pore names keep the UniProt candidate key but replace database tokens with
  // human-readable descriptors. Size/state/variant modifiers come only from the
  // actual record ID and observed fields; never infer variants from pore geometry.
  function poreDisplayName(p) {
    const tokens = String(p.pore_record_id || "").split("_").slice(1);
    const mod = [];
    if (tokens.includes("small")) mod.push("Small");
    else if (tokens.includes("large")) mod.push("Large");
    else if (tokens.includes("narrow")) mod.push("Narrow");
    else if (tokens.includes("wide")) mod.push("Wide");

    const mutation = tokens.find(t => /^[A-Z]\d+[A-Z]$/.test(t));
    if (mutation) mod.push(mutation);
    else if (tokens.includes("pmut")) mod.push("Pore-loop mutant");
    else if (tokens.includes("3xHis")) mod.push("3×His-tagged");
    else if (tokens.includes("tdNfsB")) mod.push("tdNfsB-loaded");
    else if (tokens.includes("DyP")) mod.push("DyP-loaded");
    else if (tokens.includes("EncFtn")) mod.push("EncFtn-loaded");
    else if (tokens.includes("loaded")) mod.push("Cargo-loaded");

    const site = p.pore_type === "2fold_adjacent" ? "adjacent 2-fold"
      : p.pore_type === "5fold_adjacent" ? "adjacent 5-fold"
      : poreLabel(p.pore_type);
    const siteText = `${mod.length ? `${mod.join(" ")} ` : ""}${site} pore`.replace(/^./, ch => ch.toUpperCase());
    const structure = tokens.find(t => /^\d[A-Za-z0-9]{3}$/.test(t));
    const phSuffix = tokens.some(t => t === "30" || t === "75") && p.pH != null
      ? ` (pH ${p.pH})` : "";
    return `${p.candidate_id}: ${siteText}${structure ? ` (${structure})` : phSuffix}`;
  }

  function poreCard(p) {
    const linked = citationsByRecord.get(`pores:${p.pore_record_id}`) || [];
    // Show Source DOI separately only if it is not already linked in Source.
    const extraDois = String(p.source_doi || "").split(";").map(x => x.trim()).filter(Boolean)
      .filter(doi => !linked.some(c => String(c.doi || "").toLowerCase() === doi.toLowerCase()));
    return `
      <article class="pore-card">
        <div class="assembly-top">
          <div>
            <div class="assembly-display-name">${esc(poreDisplayName(p))}</div>
            <div class="chips">
              <span class="chip">${esc(poreLabel(p.pore_type))}</span>
              <span class="chip">${esc(humanValue(p.pore_state))}</span>
              <span class="chip">${esc(poreDiameter(p))}</span>
            </div>
          </div>
        </div>
        <div class="property-grid compact-grid">
          ${enumProperty("Exterior charge", p.charge_exterior)}
          ${enumProperty("Interior charge", p.charge_interior)}
          ${enumProperty("Diameter basis", p.diameter_basis)}
          ${enumProperty("Observed dynamics", p.dynamic_status)}
        </div>
        <details class="details pore-details">
          <summary>Pore observation details</summary>
          <div class="property-grid">
            ${property("Record ID", p.pore_record_id)}
            ${property("Construct", p.construct)}
            ${enumProperty("Variant status", p.variant_status)}
            ${property("pH", p.pH)}
            ${propertyPdb("Structure ID", p.structure_id)}
            ${property("Method", p.method)}
            ${property("Source", p.source)}
          </div>
          ${p.condition ? `<section class="readable-panel condition-panel" aria-label="Experimental conditions">
            <h4>Experimental conditions</h4>${readableText(p.condition, "condition")}
          </section>` : ""}
          ${p.notes ? `<section class="readable-panel notes-panel" aria-label="Pore notes">
            <h4>Additional notes</h4>${readableText(p.notes, "pore")}
          </section>` : ""}
          ${extraDois.length ? `<p class="extra-source"><b>Additional source DOI:</b> ${extraDois.map(d => doiLink(d)).join(", ")}</p>` : ""}
        </details>
        ${citationBlock("pores", p.pore_record_id)}
      </article>`;
  }


function sequenceCard(s) {
  const sourceLink = s.source_nucleotide
    ? `<a class="ext-link" href="${esc(s.source_nucleotide)}" target="_blank" rel="noopener">${esc(display(s.nucleotide_accession))}</a>`
    : esc(display(s.nucleotide_accession));

  return `
    <article class="assembly-card sequence-card">
      <div class="assembly-top">
        <div>
          <div class="assembly-display-name">${esc(s.candidate_id)}: ${s.genomic_sequence ? "Genomic sequence" : "Sequence reference"}</div>
        </div>
      </div>

      <div class="property-grid">
        ${property("Protein accession", s.protein_accession)}
        <div class="prop">
          <span class="k">Nucleotide accession</span>
          <span class="v">${sourceLink}</span>
        </div>
        ${property("Database", s.source_database)}
        ${property("CDS start", s.cds_start)}
        ${property("CDS end", s.cds_end)}
        ${property("Strand", strandLabel(s.strand))}
        ${property("CDS length", s.cds_length_nt ? `${s.cds_length_nt} nt` : null)}
      </div>

      ${s.genomic_sequence ? `
        <details class="details">
          <summary>Genomic sequence</summary>
          <p style="overflow-wrap:anywhere;font-family:monospace;">${esc(s.genomic_sequence)}</p>
        </details>
      ` : ""}

      ${s.notes ? `
        <details class="details">
          <summary>Sequence notes</summary>
          <div class="readable-panel">${readableText(s.notes, "sequence")}</div>
        </details>
      ` : ""}
      <details class="details record-meta">
        <summary>Technical record ID</summary>
        <code>${esc(s.sequence_link_id)}</code>
      </details>
    </article>`;
}
  // Display labels change presentation only. assembly_id remains the stable reference
  // for pore observations, citations, filtering, and scientific traceability.
  const assemblyDisplayLabels = {
    'A0A0F5HPP7_Glass9_T4': 'Glass9 pore-deletion variant (T=4)',
    'A0A0F5HPP7_Letter11_T3': 'Letter11 pore-deletion variant (T=3)',
    'A0A0F5HPP7_Letter11_T4': 'Letter11 pore-deletion variant (T=4)',
    'A0A0F5HPP7_T4GALA_T4': 'T4GALA E-loop variant (T=4)',
    'A0A0F5HPP7_T4_Fdx_loaded': 'Ferredoxin-loaded T=4',
    'A0A0F5HPP7_T4_empty': 'Wild-type cargo-free T=4',
    'A0A0F5HPP7_ref': 'IMEF-loaded wild-type T=4',
    'A0A1G9WS71_N198W_T4': 'N198W pore variant (T=4)',
    'A0A1G9WS71_ref': 'Wild-type cargo-free T=4',
    'A0A502IA18_exp': 'Experimentally observed putative encapsulin particles',
    'A0AAT8XUH9_ref': 'DyP-loaded wild-type T=1',
    'A0R4H0_ref': 'Native DyP-loaded wild-type T=1',
    'D0LZ74_T1_empty': 'Wild-type cargo-free T=1',
    'D0LZ74_ref': 'EncFtn-loaded wild-type T=1',
    'I3E3I1_ref': 'Wild-type cargo-free T=4',
    'I6WZG6_His_T1_empty': 'His-tagged cargo-free T=1',
    'I6WZG6_T1_DyP_loaded': 'DyP-loaded wild-type T=1',
    'I6WZG6_partial_48mer': 'Wild-type partial 48-mer',
    'I6WZG6_partial_52mer': 'Wild-type partial 52-mer',
    'I6WZG6_partial_54mer': 'Wild-type partial 54-mer',
    'I6WZG6_ref': 'Wild-type T=1 shell',
    'K5BEG2_ref': 'Wild-type cargo-free T=1',
    'K7RV67_ref': 'Wild-type cargo-free T=1',
    'Q0SE23_DypB_loaded': 'DypB-loaded wild-type T=1',
    'Q0SE23_ref': 'Wild-type T=1 shell',
    'Q1D6H4_3xHis_T1': '3×His-tagged T=1',
    'Q1D6H4_3xHis_Tet': '3×His-tagged tetrahedral 36-mer',
    'Q1D6H4_T1': 'Wild-type T=1',
    'Q1D6H4_T3': 'Wild-type T=3',
    'Q1D6H4_T3_loaded': 'Cargo-loaded T=3',
    'Q1D6H4_pmut_T1': 'Pore-loop mutant, cargo-free T=1',
    'Q1D6H4_pmut_T3': 'Pore-loop mutant, cargo-loaded T=3',
    'Q1D6H4_pmut_T4': 'Pore-loop mutant, cargo-loaded T=4',
    'Q1Q6L7_delta_cyt': 'cEnc ΔCyt variant (T=3)',
    'Q1Q6L7_full': 'cEnc with cytochrome domain (T=3)',
    'Q2RVS0_T1_EncFtn_loaded': 'EncFtn-loaded wild-type T=1',
    'Q2RVS0_ref': 'Wild-type cargo-free T=1',
    'Q45296_T1_DyP_loaded': 'DyP-loaded wild-type T=1',
    'Q45296_ref': 'Wild-type cargo-free T=1',
    'Q55032_T1_empty': 'Wild-type apo-SrpI T=1',
    'Q55032_ref': 'CyD-loaded wild-type T=1',
    'Q8U1L4_ref': 'Native ferritin-encapsulin fusion (T=3)',
    'Q9WZP2_S1K_T1': 'S1K pore mutant (T=1)',
    'Q9WZP2_S1R_T1': 'S1R pore mutant (T=1)',
    'Q9WZP2_S3E_T1': 'S3E pore mutant (T=1)',
    'Q9WZP2_S5D_T1': 'S5D pore-loop variant (T=1)',
    'Q9WZP2_S6E_T1': 'S6E pore-loop variant (T=1)',
    'Q9WZP2_S7D_T1': 'S7D pore-loop variant (T=1)',
    'Q9WZP2_S7G_T1': 'S7G pore-loop deletion (T=1)',
    'Q9WZP2_T1_empty': 'Wild-type cargo-free T=1',
    'Q9WZP2_ref': 'FLP-associated wild-type T=1',
  };

  function assemblyDisplayName(a) {
    const fallbackConstruct = String(a.construct || "").trim();
    const suffix = a.T_number == null ? "" : ` (T=${a.T_number})`;
    const fallback = fallbackConstruct && fallbackConstruct.toLowerCase() !== "enc"
      ? `${fallbackConstruct}${suffix}`
      : `${a.variant_status === "engineered" ? "Engineered" : "Wild-type"} assembly${suffix}`;
    return `${a.candidate_id}: ${assemblyDisplayLabels[a.assembly_id] || fallback}`;
  }

  // Break only at unambiguous sentence boundaries (punctuation + uppercase).
  // This avoids splitting abbreviations like "E. coli" and "et al. 2022".
  // Wording is never rewritten; strings are escaped before rendering.
  function readableSegments(value, separateSemicolons=false) {
    const text = String(value || "").replace(/\s+/g, " ").trim();
    if (!text) return [];
    const sentences = text.split(/(?<=[.!?])\s+(?=[A-Z])/u).filter(Boolean);
    if (!separateSemicolons) return sentences;
    return sentences.flatMap(sentence => sentence.split(/;\s+(?=\S)/u).map(x => x.trim()).filter(Boolean));
  }

  function readableText(value, kind="notes") {
    const lines = readableSegments(value, ["condition", "sequence", "pore"].includes(kind));
    if (!lines.length) return '<p class="readable-empty">Not reported</p>';
    // Even one short sequence/pore note is a bullet for consistent scanability.
    if (lines.length === 1 && !["sequence", "pore"].includes(kind)) return `<p class="readable-prose">${esc(lines[0])}</p>`;
    return `<ul class="readable-points">${lines.map(t => `<li>${esc(t)}</li>`).join("")}</ul>`;
  }

  function assemblyCard(a, refId, matchState="") {
    const linkedPores = poresByAssembly.get(a.assembly_id) || [];
    const variantChip = a.variant_status === "wild_type"
      ? `<span class="chip wt">WT</span>`
      : `<span class="chip eng">Engineered</span>`;
    const refChip = refId === a.assembly_id ? `<span class="chip ref">Reference assembly</span>` : "";
    const unknownChip = matchState === "potential" ? `<span class="chip unknown">Missing required data</span>` : "";
    const sequenceStatus = a.shell_sequence_status === "modified" ? "modified" : "unmodified";
    const sequenceChip = sequenceStatus === "modified"
      ? `<span class="chip eng">Modified shell</span>`
      : `<span class="chip wt">Unmodified shell</span>`;
    const modificationNote = sequenceStatus === "modified" ? (() => {
      const pos = a.shell_change_reference_positions_aa;
      const before = a.shell_change_original_aa;
      const after = a.shell_change_variant_aa;
      const hasBefore = typeof before === 'string' && before.length > 0;
      const hasAfter = typeof after === 'string' && after.length > 0;
      return `<section class="sequence-change-panel" aria-label="Shell protein modification details">
        <div class="change-head"><strong>Shell protein modification</strong>
          <span class="change-location">${pos ? `Reference position: ${esc(pos)} aa` : 'Position not verified'}</span></div>
        ${a.shell_sequence_change ? `<p class="change-description">${esc(a.shell_sequence_change)}</p>` : ''}
        ${hasBefore || hasAfter ? `<div class="change-residues">
          ${hasBefore ? `<div><span class="change-label">WT reference</span><code class="change-before">${esc(before)}</code></div>` : ''}
          ${hasBefore && hasAfter ? '<span class="change-arrow" aria-hidden="true">→</span>' : ''}
          ${hasAfter ? `<div><span class="change-label">Modified</span><code class="change-after">${esc(after)}</code></div>` : ''}
          ${hasBefore && !hasAfter ? '<span class="change-arrow">→ deleted</span>' : ''}
          ${!hasBefore && hasAfter ? '<span class="change-arrow">Inserted</span>' : ''}
        </div>` : '<p class="change-unverified">Exact changed amino-acid sequence not verified.</p>'}
        ${a.shell_change_alignment_note ? `<p class="change-note">${esc(a.shell_change_alignment_note)}</p>` : ''}
      </section>`;
    })() : "";
    return `
      <article class="assembly-card">
        <div class="assembly-top">
          <div>
            <div class="assembly-display-name">${esc(assemblyDisplayName(a))}</div>
            <div class="chips">${variantChip}${refChip}${sequenceChip}${unknownChip}</div>
          </div>
          <div class="chip">${esc(a.assembly_symmetry ? humanValue(a.assembly_symmetry) : "Symmetry unknown")}</div>
        </div>
        <div class="why">${esc(assemblyWhy(a))}</div>
        ${modificationNote}
        <details class="details">
          <summary>Assembly details</summary>
        <div class="property-grid">
          ${property("Record ID", a.assembly_id)}
          ${property("Construct", a.construct)}
          ${property("Shell protein", sequenceStatus === "modified" ? "Modified" : "Unmodified")}
          ${property("T-number", a.assembly_symmetry === "tetrahedral" ? "N/A (tetrahedral)" : (a.T_number == null ? null : `T=${a.T_number}`))}
          ${property("Subunits", a.shell_subunit_count)}
          ${property("Shell diameter", a.shell_diameter_nm === null ? null : `${a.shell_diameter_nm} nm`)}
          ${property("Inner diameter", a.inner_diameter_nm === null ? null : `${a.inner_diameter_nm} nm`)}
          ${property("Wall thickness", a.wall_thickness_nm === null ? null : `${a.wall_thickness_nm} nm`)}
          ${property("Inner volume", a.inner_volume_A3 === null ? null : `${a.inner_volume_A3} Å³`)}
          ${property("Tm", a.thermostability_tm_c === null ? null : `${a.thermostability_tm_c} °C`)}
          ${propertyPdb("Structure ID", a.structure_id)}
          ${property("Method", a.method)}
        </div>
        <section class="readable-panel condition-panel" aria-label="Experimental conditions">
          <h4>Experimental conditions</h4>
          ${readableText(a.condition, "condition")}
        </section>
        <section class="readable-panel notes-panel" aria-label="Additional notes">
          <h4>Additional notes</h4>
          ${readableText(a.notes)}
        </section>
        </details>
        ${linkedPores.length ? `
          <details class="details pore-group">
            <summary>Pore observations (${linkedPores.length})</summary>
            <p class="hint">Only pores linked to this exact assembly or engineered variant are listed.</p>
            <div class="pore-list">${linkedPores.map(poreCard).join("")}</div>
          </details>` : ""}
        ${citationBlock("assemblies", a.assembly_id)}
      </article>`;
  }

  // TP records belong to a candidate protein system. Links indicate exactly which
  // Builder assemblies a TP is associated with, but are NOT blanket evidence of
  // successful loading by every engineered variant.
  function tpCard(tp) {
    const links = tpLinksById.get(tp.tp_id) || [];
    const dna = tp.builder_dna_5to3;
    return `<article class="assembly-card tp-record">
      <div class="assembly-top"><div>
        <div class="assembly-display-name">${esc(tp.tp_id)}</div>
        <p class="hint">${esc(tp.cargo_protein || 'Cargo not reported')}</p>
      </div></div>
      <div class="property-grid">
        ${property('Cargo accession', tp.cargo_accession)}
        ${enumProperty('Cargo terminus', tp.cargo_terminus)}
        ${enumProperty('TP origin', tp.tp_origin)}
        ${enumProperty('Sequence scope', tp.sequence_scope)}
        ${property('Core motif (AA)', tp.tp_core_motif_aa)}
        ${enumProperty('Builder use', tp.builder_use_status)}
        ${property('Cargo residue range', tp.cargo_residue_range)}
      </div>
      <details class="details tp-sequence-details"><summary>Amino-acid sequence (${esc(tp.tp_length_aa || tp.tp_sequence_aa?.length || 0)} aa)</summary>
        <pre class="tp-sequence" aria-label="Targeting peptide amino-acid sequence">${esc(tp.tp_sequence_aa || '')}</pre>
      </details>
      ${dna ? `<details class="details tp-sequence-details"><summary>Curated DNA sequence (5′→3′ · ${dna.length} nt)</summary>
        <pre class="tp-sequence" aria-label="Targeting peptide DNA sequence">${esc(dna)}</pre>
      </details>` : '<p class="hint tp-missing-dna">No curated DNA sequence for this TP/region. An amino-acid sequence is not experimental DNA.</p>'}
      <details class="details"><summary>Evidence and associated Builder assemblies (${links.length})</summary>
        <div class="property-grid">
          ${enumProperty('Validation evidence', tp.validation_evidence)}
          ${property('Source', tp.source)}
        </div>
        <p class="hint">A Builder association does not establish that TP loading was tested with that specific engineered shell.</p>
        ${links.length ? `<ul class="tp-associated-assemblies">${links.map(link => `<li><strong>${esc(link.assembly_id)}</strong>: ${esc(humanValue(link.builder_transfer_status))}; ${esc(humanValue(link.pair_specific_evidence_status))}</li>`).join('')}</ul>` : '<p class="hint">No Builder assembly relation curated.</p>'}
        ${tp.notes ? `<div class="readable-panel">${readableText(tp.notes)}</div>` : ''}
      </details>
      ${citationBlock('targeting_peptides', tp.tp_id)}
    </article>`;
  }

  function candidateCard(c, assemblySubset=null, stateMap=null) {
    const linked = assemblySubset ?? (byCandidate.get(c.candidate_id) || []);
    const linkedSequences = sequencesByCandidate.get(c.candidate_id) || [];
    const linkedTps = tpsByCandidate.get(c.candidate_id) || [];
    const poreCount = (byCandidate.get(c.candidate_id) || [])
      .reduce((sum, a) => sum + (poresByAssembly.get(a.assembly_id) || []).length, 0);
    const assemblyHtml = linked.length
      ? linked.map(a => assemblyCard(a, c.reference_assembly_id, stateMap?.get(a.assembly_id) || "")).join("")
      : `<div class="empty-state">No curated assembly record is available for this candidate in the current dataset.</div>`;
      const sequenceHtml = linkedSequences.length
  ? linkedSequences.map(s => sequenceCard(s)).join("")
  : `<div class="empty-state">No nucleotide sequence record is available for this candidate in the current dataset.</div>`;
    const ids = [c.gene, c.locus_tag, c.orf_name].filter(Boolean).join(" • ");
    const idDisplay = c.source_uniprot
      ? `<a class="ext-link" href="${esc(c.source_uniprot)}" target="_blank" rel="noopener">${esc(c.candidate_id)}</a>`
      : esc(c.candidate_id);
    return `
      <article class="candidate-card">
        <div class="candidate-head">
          <div>
            <h2 class="candidate-title"><i>${esc(c.organism)}</i>: ${idDisplay}</h2>
            <p class="candidate-sub">${esc(c.protein_name)}</p>
            <div class="chips">
              ${c.strain ? `<span class="chip">${esc(c.strain)}</span>` : ""}
              ${c.encapsulin_family ? `<span class="chip">${esc(humanValue(c.encapsulin_family))}</span>` : ""}
              ${ids ? `<span class="chip">${esc(ids)}</span>` : ""}
              <span class="chip">${linked.length} shown ${linked.length === 1 ? "assembly" : "assemblies"}</span>
              ${poreCount ? `<span class="chip">${poreCount} pore ${poreCount === 1 ? "observation" : "observations"}</span>` : ""}
            </div>
          </div>
          <span class="chip ref">${linked.length} assembly record${linked.length === 1 ? "" : "s"}</span>
        </div>
        <details class="details">
          <summary>Sequence data (${linkedSequences.length})</summary>
          <div class="assembly-list sequence-list">${sequenceHtml}</div>
        </details>
        ${linkedTps.length ? `<details class="details tp-group">
          <summary>Targeting peptides / cargo-targeting regions (${linkedTps.length})</summary>
          <p class="hint tp-help">The records below include both design-eligible TPs and research-only motifs/regions. Open a record to inspect its literal sequence and assembly-specific evidence.</p>
          <div class="assembly-list tp-list">${linkedTps.map(tpCard).join('')}</div>
        </details>` : ''}
        ${citationBlock("databank", c.candidate_id)}
        <div class="assembly-list">${assemblyHtml}</div>
      </article>`;
  }

  // Direct search
  function candidateSearchText(c) {
    const linked = byCandidate.get(c.candidate_id) || [];
    const linkedSequences = sequencesByCandidate.get(c.candidate_id) || [];
    const linkedTps = tpsByCandidate.get(c.candidate_id) || [];
    const linkedPores = linked.flatMap(a => poresByAssembly.get(a.assembly_id) || []);
    const sourceLinks = [
      ...(citationsByRecord.get(`databank:${c.candidate_id}`) || []),
      ...linked.flatMap(a => citationsByRecord.get(`assemblies:${a.assembly_id}`) || []),
      ...linkedPores.flatMap(p => citationsByRecord.get(`pores:${p.pore_record_id}`) || []),
      ...linkedTps.flatMap(tp => citationsByRecord.get(`targeting_peptides:${tp.tp_id}`) || [])
    ];
    return norm([
      c.candidate_id, c.entry_name, c.protein_name, c.organism, c.strain,
      c.genus, c.gene, c.locus_tag, c.orf_name, c.encapsulin_family,
      ...linked.map(a => a.construct),
      ...linkedTps.flatMap(tp => [tp.tp_id, tp.cargo_protein, tp.tp_sequence_aa, tp.tp_core_motif_aa]),
      ...linkedPores.flatMap(p => [p.pore_record_id, p.pore_type, p.construct, p.structure_id]),
      ...sourceLinks.flatMap(link => [link.doi, link.citation_label]),
...linkedSequences.flatMap(s => [
  s.protein_accession,
  s.nucleotide_accession,
  s.sequence_link_id
])
    ].filter(Boolean).join(" | "));
  }

  const searchIndex = candidates.map(c => ({c, text:candidateSearchText(c)}));

  function runSearch() {
    const q = norm($("globalSearch").value);
    if (!q) {
      $("searchSummary").textContent = "Type a query to search all database candidates.";
      $("searchResults").innerHTML = "";
      return;
    }
    const tokens = q.split(" ").filter(Boolean);
    const hits = searchIndex.filter(x => tokens.every(t => x.text.includes(t)));
    $("searchSummary").textContent =
      `${hits.length} candidate${hits.length === 1 ? "" : "s"} found.`;
    $("searchResults").innerHTML = hits.length
      ? hits.map(x => candidateCard(x.c)).join("")
      : `<div class="empty-state">No candidate matched this search.</div>`;
  }
  $("globalSearch").addEventListener("input", runSearch);
  runSearch();

  function intervalRelation(helper, minVal, maxVal) {
    if (!helper) return "unknown";
    const minParsed = readLocaleNumber(minVal);
    const maxParsed = readLocaleNumber(maxVal);
    if (!minParsed.valid || !maxParsed.valid) return "invalid";
    const reqMin = minParsed.empty ? -Infinity : minParsed.value;
    const reqMax = maxParsed.empty ? Infinity : maxParsed.value;
    return (helper.max < reqMin || helper.min > reqMax) ? "fail" : "pass";
  }

  // A match needs one *observed pore row* on this specific assembly satisfying
  // every pore criterion. Never combine diameter from one pore with the charge
  // of a different pore, nor values from other assemblies of the same protein.
  function classifyPores(a) {
    const poreType = $("poreType").value;
    const poreState = $("poreState").value;
    const poreCharge = $("poreCharge").value;
    const min = readLocaleNumber($("poreDiameterMin").value);
    const max = readLocaleNumber($("poreDiameterMax").value);
    const needsDiameter = !min.empty || !max.empty;
    if (!poreType && !poreState && !poreCharge && !needsDiameter) return "match";
    const rows = poresByAssembly.get(a.assembly_id) || [];
    if (!rows.length) return "potential";
    const relevant = rows.filter(p => (!poreType || p.pore_type === poreType) &&
      (!poreState || p.pore_state === poreState));
    if (!relevant.length) return "potential"; // No measurement of requested pore type/state.
    let hasUnknown = false;
    for (const p of relevant) {
      let missing = false;
      if (needsDiameter) {
        const d = p.pore_diameter_nm;
        if (typeof d !== "number" || !Number.isFinite(d)) missing = true;
        else if ((!min.empty && d < min.value) || (!max.empty && d > max.value)) continue;
      }
      if (poreCharge) {
        if (!p.charge_exterior || p.charge_exterior === "not_reported") missing = true;
        else if (p.charge_exterior !== poreCharge) continue;
      }
      if (!missing) return "match";
      hasUnknown = true;
    }
    return hasUnknown ? "potential" : "no";
  }

  function classify(a) {
    let unknown = false;
    const dmin = $("diameterMin").value;
    const dmax = $("diameterMax").value;

    if (dmin !== "" || dmax !== "") {
      const rel = intervalRelation(a._shell_diameter, dmin, dmax);
      if (rel === "fail") return "no";
      if (rel === "unknown") unknown = true;
      if (rel === "invalid") return "no";
    }

    const t = $("tNumber").value;
    if (t) {
      if (a.T_number === null || a.T_number === "") unknown = true;
      else if (String(a.T_number) !== t) return "no";
    }

    const variant = $("variantStatus").value;
    if (variant && a.variant_status !== variant) return "no";

    const sym = $("symmetry").value;
    if (sym) {
      if (!a.assembly_symmetry) unknown = true;
      else if (a.assembly_symmetry !== sym) return "no";
    }

    const sub = $("subunitCount").value;
    if (sub) {
      if (a.shell_subunit_count === null || a.shell_subunit_count === "") unknown = true;
      else if (String(a.shell_subunit_count) !== sub) return "no";
    }

    if ($("structureRequired").checked && !a.structure_id) return "no";

    const poreState = classifyPores(a);
    if (poreState === "no") return "no";
    if (poreState === "potential") unknown = true;
    return unknown ? "potential" : "match";
  }

  function prefKey(a) {
    const targetRaw = $("targetDiameter").value;
    const targetParsed = readLocaleNumber(targetRaw);
    const preferStructure = $("preferStructure").checked;
    let diameterUnknown = 0, distance = 0;
    if (targetParsed.valid && !targetParsed.empty) {
      if (a._shell_diameter && Number.isFinite(a._shell_diameter.center)) {
        distance = Math.abs(a._shell_diameter.center - targetParsed.value);
      } else {
        diameterUnknown = 1;
        distance = Number.POSITIVE_INFINITY;
      }
    }
    const structurePenalty = preferStructure ? (a.structure_id ? 0 : 1) : 0;
    return [diameterUnknown, distance, structurePenalty, a.assembly_id];
  }

  function comparePref(a,b) {
    const ka = prefKey(a), kb = prefKey(b);
    for (let i=0; i<ka.length; i++) {
      if (ka[i] < kb[i]) return -1;
      if (ka[i] > kb[i]) return 1;
    }
    return 0;
  }

  function groupedAssemblyResults(list, state) {
    const groups = new Map();
    list.forEach(a => {
      if (!groups.has(a.candidate_id)) groups.set(a.candidate_id, []);
      groups.get(a.candidate_id).push(a);
    });
    return [...groups.entries()].map(([cid, rows]) => {
      const c = candidateMap.get(cid);
      const sm = new Map(rows.map(r => [r.assembly_id, state]));
      return candidateCard(c, rows, sm);
    }).join("");
  }

  function runFinder() {
    if (!validateFinderInputs()) {
      $("finderSummary").textContent = "Check the numeric filter values.";
      $("matchResults").innerHTML = "";
      $("potentialResults").innerHTML = "";
      return;
    }
    const states = assemblies.map(a => ({a, state:classify(a)}));
    let matches = states.filter(x => x.state === "match").map(x => x.a).sort(comparePref);
    let potentials = states.filter(x => x.state === "potential").map(x => x.a).sort(comparePref);

    if (!$("includeUnknown").checked) potentials = [];

    $("finderSummary").textContent =
      `${matches.length} match${matches.length === 1 ? "" : "es"}`
      + (potentials.length ? ` • ${potentials.length} potential match${potentials.length === 1 ? "" : "es"}` : "");

    $("matchResults").innerHTML = matches.length
      ? groupedAssemblyResults(matches, "match")
      : `<div class="empty-state">No curated assembly is known to satisfy all required filters.</div>`;

    $("potentialResults").innerHTML = potentials.length
      ? groupedAssemblyResults(potentials, "potential")
      : `<div class="empty-state">No potential matches to show.</div>`;
    $("potentialBlock").classList.toggle("hidden", !$("includeUnknown").checked);
  }

  [
    "diameterMin","diameterMax","tNumber","variantStatus","symmetry",
    "subunitCount","structureRequired","includeUnknown","targetDiameter","preferStructure",
    "poreType","poreState","poreCharge","poreDiameterMin","poreDiameterMax"
  ].forEach(id => $(id).addEventListener("input", runFinder));

  $("searchCapsules").addEventListener("click", runFinder);

  $("clearFilters").addEventListener("click", () => {
    ["diameterMin","diameterMax","tNumber","variantStatus","symmetry","subunitCount","targetDiameter",
      "poreType","poreState","poreCharge","poreDiameterMin","poreDiameterMax"]
      .forEach(id => $(id).value = "");
    $("structureRequired").checked = false;
    $("preferStructure").checked = false;
    $("includeUnknown").checked = true;
    runFinder();
  });

  runFinder();

  // Keep tab, filters, search text and scroll position across a page refresh.
  const SESSION_KEY = "encapsulin.selector.v1";
  const TEXT_IDS = ["globalSearch","diameterMin","diameterMax","tNumber","variantStatus","symmetry","subunitCount","targetDiameter",
    "poreType","poreState","poreCharge","poreDiameterMin","poreDiameterMax"];
  const CHECK_IDS = ["structureRequired","includeUnknown","preferStructure"];
  const activeMode = () => document.querySelector(".mode-tab.active").dataset.mode;

  function saveSession() {
    try {
      const s = { mode: activeMode(), scrollY: window.scrollY, text: {}, checks: {} };
      TEXT_IDS.forEach(id => s.text[id] = $(id).value);
      CHECK_IDS.forEach(id => s.checks[id] = $(id).checked);
      sessionStorage.setItem(SESSION_KEY, JSON.stringify(s));
    } catch (e) {}
  }

  (function restoreSession() {
    let s = null;
    try { s = JSON.parse(sessionStorage.getItem(SESSION_KEY)); } catch (e) {}
    if (!s) { if (modeFromHash()) setMode(modeFromHash()); return; }
    TEXT_IDS.forEach(id => { if (s.text && s.text[id] !== undefined) $(id).value = s.text[id]; });
    CHECK_IDS.forEach(id => { if (s.checks && s.checks[id] !== undefined) $(id).checked = s.checks[id]; });
    const mode = modeFromHash() || s.mode;
    if (document.querySelector(`.mode-tab[data-mode="${mode}"]`)) {
      setMode(mode);
      history.replaceState(null, "", "#" + mode);
    }
    runSearch();
    runFinder();
    history.scrollRestoration = "manual";
    window.scrollTo({ top: s.scrollY || 0, behavior: "instant" });
  })();

  window.addEventListener("pagehide", saveSession);
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "hidden") saveSession(); });

  const sanity = assemblies.filter(a => String(a.T_number) === "1" && a._shell_diameter && a._shell_diameter.max >= 0.1 && a._shell_diameter.min <= 40);
  console.info(`Selector sanity check: expected 26 current matches for 0.1 to 40 nm + T=1; found ${sanity.length}.`);
})();


// Light/dark mode, shared with the builder through localStorage.
(function initTheme() {
  const SUN = '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M5 19l1.5-1.5M17.5 6.5L19 5"/>';
  const MOON = '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>';
  const root = document.documentElement;
  function sync() {
    const dark = root.getAttribute("data-theme") === "dark";
    document.getElementById("themeLabel").textContent = dark ? "Dark" : "Light";
    document.getElementById("themeIcon").innerHTML = dark ? MOON : SUN;
  }
  document.getElementById("themeToggle").addEventListener("click", () => {
    const dark = root.getAttribute("data-theme") !== "dark";
    root.setAttribute("data-theme", dark ? "dark" : "light");
    try { localStorage.setItem("encore.theme", dark ? "dark" : "light"); } catch (e) {}
    sync();
  });
  sync();
})();

// The note about how the filters work sits behind an info button next to the tabs
(function(){
  const btn=document.getElementById('alphaInfoBtn'), panel=document.getElementById('alphaInfo');
  if(!btn||!panel) return;
  btn.addEventListener('click',()=>{ const open=panel.hidden; panel.hidden=!open; btn.setAttribute('aria-expanded',String(open)); });
})();
