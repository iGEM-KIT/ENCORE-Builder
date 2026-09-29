(() => {
  const DATA = window.ENCAPSULIN_SELECTOR_DATA;
  const candidates = DATA.candidates;
  const assemblies = DATA.assemblies;

  const byCandidate = new Map();
  assemblies.forEach(a => {
    if (!byCandidate.has(a.candidate_id)) byCandidate.set(a.candidate_id, []);
    byCandidate.get(a.candidate_id).push(a);
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
      ["targetDiameter", "Preferred diameter"]
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
    const box = $("filterError");
    if (box) {
      box.textContent = errors.join(" ");
      box.classList.toggle("hidden", errors.length === 0);
    }
    return errors.length === 0;
  }

  $("datasetBadge").textContent =
    `${DATA.meta.candidate_count} candidates • ${DATA.meta.assembly_count} curated assemblies`;
  $("alphaNote").textContent = DATA.meta.status_note;

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
    const o = document.createElement("option"); o.value=v; o.textContent=v; $("symmetry").appendChild(o);
  });
  unique("shell_subunit_count").forEach(v => {
    const o = document.createElement("option"); o.value=v; o.textContent=v; $("subunitCount").appendChild(o);
  });

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

  function assemblyCard(a, refId, matchState="") {
    const variantChip = a.variant_status === "wild_type"
      ? `<span class="chip wt">WT</span>`
      : `<span class="chip eng">Engineered</span>`;
    const refChip = refId === a.assembly_id ? `<span class="chip ref">Reference assembly</span>` : "";
    const unknownChip = matchState === "potential" ? `<span class="chip unknown">Missing required data</span>` : "";
    return `
      <article class="assembly-card">
        <div class="assembly-top">
          <div>
            <div class="assembly-id">${esc(a.assembly_id)}</div>
            <div class="chips">${variantChip}${refChip}${unknownChip}</div>
          </div>
          <div class="chip">${esc(a.assembly_symmetry || "symmetry unknown")}</div>
        </div>
        <div class="why">${esc(assemblyWhy(a))}</div>
        <div class="property-grid">
          ${property("Construct", a.construct)}
          ${property("T-number", a.T_number === null ? null : `T=${a.T_number}`)}
          ${property("Subunits", a.shell_subunit_count)}
          ${property("Shell diameter", a.shell_diameter_nm === null ? null : `${a.shell_diameter_nm} nm`)}
          ${property("Inner diameter", a.inner_diameter_nm === null ? null : `${a.inner_diameter_nm} nm`)}
          ${property("Wall thickness", a.wall_thickness_nm === null ? null : `${a.wall_thickness_nm} nm`)}
          ${property("Inner volume", a.inner_volume_A3 === null ? null : `${a.inner_volume_A3} Å³`)}
          ${property("Tm", a.thermostability_tm_c === null ? null : `${a.thermostability_tm_c} °C`)}
          ${property("Structure ID", a.structure_id)}
          ${property("Method", a.method)}
          ${property("Condition", a.condition)}
          ${property("Source", a.source)}
        </div>
        <details class="details">
          <summary>Notes</summary>
          <p>${esc(display(a.notes))}</p>
        </details>
      </article>`;
  }

  function candidateCard(c, assemblySubset=null, stateMap=null) {
    const linked = assemblySubset ?? (byCandidate.get(c.candidate_id) || []);
    const assemblyHtml = linked.length
      ? linked.map(a => assemblyCard(a, c.reference_assembly_id, stateMap?.get(a.assembly_id) || "")).join("")
      : `<div class="empty-state">No curated assembly record is available for this candidate in the current dataset.</div>`;
    const ids = [c.gene, c.locus_tag, c.orf_name].filter(Boolean).join(" • ");
    const idDisplay = c.source_uniprot
      ? `<a class="uniprot-link" href="${esc(c.source_uniprot)}" target="_blank" rel="noopener">${esc(c.candidate_id)}</a>`
      : esc(c.candidate_id);
    return `
      <article class="candidate-card">
        <div class="candidate-head">
          <div>
            <h2 class="candidate-title"><i>${esc(c.organism)}</i> — ${idDisplay}</h2>
            <p class="candidate-sub">${esc(c.protein_name)}</p>
            <div class="chips">
              ${c.strain ? `<span class="chip">${esc(c.strain)}</span>` : ""}
              ${c.encapsulin_family ? `<span class="chip">${esc(c.encapsulin_family)}</span>` : ""}
              ${ids ? `<span class="chip">${esc(ids)}</span>` : ""}
              <span class="chip">${linked.length} curated ${linked.length === 1 ? "assembly" : "assemblies"}</span>
            </div>
          </div>
        </div>
        <div class="assembly-list">${assemblyHtml}</div>
      </article>`;
  }

  // Direct search
  function candidateSearchText(c) {
    const linked = byCandidate.get(c.candidate_id) || [];
    return norm([
      c.candidate_id, c.entry_name, c.protein_name, c.organism, c.strain,
      c.genus, c.gene, c.locus_tag, c.orf_name, c.encapsulin_family,
      ...linked.map(a => a.construct)
    ].filter(Boolean).join(" | "));
  }

  const searchIndex = candidates.map(c => ({c, text:candidateSearchText(c)}));

  function runSearch() {
    const q = norm($("globalSearch").value);
    if (!q) {
      $("searchSummary").textContent = "Type a query to search all databank candidates.";
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
    "subunitCount","structureRequired","includeUnknown","targetDiameter","preferStructure"
  ].forEach(id => $(id).addEventListener("input", runFinder));

  $("searchCapsules").addEventListener("click", runFinder);

  $("clearFilters").addEventListener("click", () => {
    ["diameterMin","diameterMax","tNumber","variantStatus","symmetry","subunitCount","targetDiameter"]
      .forEach(id => $(id).value = "");
    $("structureRequired").checked = false;
    $("preferStructure").checked = false;
    $("includeUnknown").checked = true;
    runFinder();
  });

  runFinder();

  // Keep tab, filters, search text and scroll position across a page refresh.
  const SESSION_KEY = "encapsulin.selector.v1";
  const TEXT_IDS = ["globalSearch","diameterMin","diameterMax","tNumber","variantStatus","symmetry","subunitCount","targetDiameter"];
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
  console.info(`Selector sanity check: expected 26 current matches for 0.1–40 nm + T=1; found ${sanity.length}.`);
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
