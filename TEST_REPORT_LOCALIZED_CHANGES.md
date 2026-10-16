# ENCORE: Left sidebar + localized shell-protein changes — 16 October 2026

## Passed tests

- JavaScript syntax check: `selector-alpha.js`, `builder-filter.js`, `selector-data.js`
- JavaScript smoke test: `node scripts/test-encore-simplified-ui.cjs`
  - 24 approved CDS designs shown without filtering
  - Left-hand Builder filter panel, WT/Engineered filter and reset
  - Direct handoff of the approved Letter11 DNA sequence to the Builder
  - Sequence comparisons for `Q1D6H4_3xHis_T1` (KTG → HHH, reference 199–201),
    `Q1D6H4_pmut` (reference 196–203), `Q9WZP2_S1K_T1` (187),
    `A0A0F5HPP7_Letter11_T4` (193–209)
  - Explicit uncertainty for the unrecovered `I6WZG6` C-terminal His-tag
- Excel ↔ JSON sync: `python scripts/export-excel-to-json.py --check`
  - 390/390 exported data files match; 74 candidates, 51 assemblies,
    56 pore observations, 131 evidence records, 24 approved designs
- HTTP preview: homepage, both filters, JS bundles and data bundles return 200
- 20/20 modified assemblies have a documented position or insertion site; 19/20 have sequence details, and the one unrecovered His-tag is not guessed

## Restrictions and scientific notes

- `Q1D6H4_pmut`: the curated published deletion label is I195–L202, whereas
  alignment to the reference **287-aa EncA protein** maps I196–L203.
  These are shown as different numbering conventions, not silently reconciled.
- Positions are 1-based and apply to the reference **protein**, not the DNA,
  not to an alternate deposited tag, and not to a guarantee of plasmid identity.
- The 4 pre-existing incomplete pore charge annotations remain null in the
  generated JSON; this change does not re-curate those pores.
- The headless browser rendering attempt was unavailable. The pages and their
  behavior have been checked through HTTP + JavaScript unit simulations;
  visual spacing still benefits from inspection on Windows.
- The full Builder calculation backend was not re-tested; the lightweight
  preview server exposes its original interface, not the calculation APIs.
