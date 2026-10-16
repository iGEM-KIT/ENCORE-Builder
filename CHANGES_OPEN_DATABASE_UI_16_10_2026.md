# ENCORE Open Database — interface updates (16 October 2026)

This release modifies **presentation only**. It uses the same source Excel, JSON files, 24 approved Builder CDS entries, scientific values, and original classic Explorer/Builder logic as the preceding release.

Changes:
- The shared site navigation consistently reads **ENCORE Builder | Open Database**.
- Removed the redundant green “OPEN ENCAPSULIN DATABANK” eyebrow text.
- The Overview now begins “Welcome to the Open Database”, and public-facing Database terminology is consistent without renaming the underlying XLSX or data keys.
- Removed the “Common questions” section and its shortcut.
- Added a visual explanation of **CDS (DNA) → amino-acid sequence → possible shell assemblies**, including the difference between synonymous DNA changes and distinct protein architectures. EncA WT T=1 / T=3 illustrates one protein with more than one documented assembly.
- Added the scientifically important caution on **reported T-number/diameter versus experimental outcomes** to the Builder Filter.

## One source of scientific data

Both tools use the same `encapsulin_selector/data/Open_Encapsulin_Databank.xlsx` scientific workbook.

- `py scripts/export-excel-to-json.py --write` regenerates the JSON scientific records and the 24-entry approved `builder_catalog.json`.
- `node scripts/build-selector-data.mjs` regenerates `encapsulin_selector/selector-data.js` and `builder-catalog.js` from those files.
- Explore Encapsulins displays the full scientific dataset; Builder Filter displays the 24 reviewed sequences combined with structural properties from that **same** dataset.

**There is no second independently maintained scientific database.** Two browser-facing generated files do not mean two underlying data sources.

## Verification

- `py scripts/export-excel-to-json.py --check` — 390 files unchanged; 24 approved CDS; 74 candidates; 51 assemblies.
- `node scripts/test-encore-simplified-ui.cjs` — validated Builder Filter and mutation comparison.
- `py scripts/test-encore-overview.py` — validated all three screens, links, glossary and new section.
- Browser screenshots were not possible because the automated browser environment blocked page navigation.

Four pore charge annotations are still flagged for scientific manual review; this release does not modify them.
