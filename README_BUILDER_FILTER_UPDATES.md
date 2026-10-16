# Builder Filter — scientific sources, visible sequences, cargo-free context

This release builds on `ENCORE_Open_Database_Overview_Header_16_10_2026.zip` without redesigning Overview, Explore Encapsulins, or the Builder.

## User-facing changes

1. **Source:** each eligible sequence card shows the exact selected assembly's curated article citations. If a DOI is available, the citation opens `doi.org`. PDB links are also included where present. A publication that lacks a verified DOI stays as a text source instead of receiving a fabricated link. Sources for a different pore mutant or construct are not automatically attributed to the chosen assembly.
2. **View transferred DNA sequence:** expand the `View transferred DNA sequence` section of any card to see the exact approved shell CDS in the 5′→3′ coding orientation. The CDS starts collapsed. `Copy CDS` copies those same nucleotides to the clipboard, if the browser permits clipboard access. `Select for Builder` continues to transfer that same approved CDS directly to Builder.
3. **Cargo context:** every option transfers **shell-only CDS**; neither cargo protein nor targeting peptide is included. Cards show `Cargo-free assembly` only when the assembly's curated `condition` explicitly describes an empty/apo/cargo-free preparation. For the three entries whose `condition` does not explicitly establish this, the card says `Experimental cargo state not specified`. This avoids turning a shell-only Builder design into an unverified claim about the experimental preparation.

## Source of truth and data

Both Builder Filter and Explore Encapsulins continue to use the same public Excel master (`encapsulin_selector/data/Open_Encapsulin_Databank.xlsx`) via the existing export scripts. The Builder Filter builds source links dynamically from the assembly-specific `citation_links`, `source_doi`, `source` and `structure_id` fields in generated `selector-data.js`; no duplicated bibliography was added.

**No scientific data or spreadsheet cells were changed in this release.** The existing approved 24 CDS remain unchanged.

## Local preview

```powershell
py scripts/preview_ui.py
```

Open `http://127.0.0.1:8080/selector/builder-filter.html`.

## Checks

```powershell
node --test tests/unit/selector/simple-filter.test.mjs tests/unit/selector/builder-visibility.test.mjs
node scripts/test-encore-simplified-ui.cjs
py scripts/test-encore-overview.py
py scripts/export-excel-to-json.py --check
```

Note: `preview_ui.py` is a UI-only preview; computation features in the full Builder require its original backend. Browser-automated visual navigation was blocked in the packaging environment, so the dropdown visuals and copy action should also be checked manually in VS Code/your browser.
