# ENCORE — Original GitLab selector + simplified Databank

This release is built **from the user-provided `ENCORE-Builder-main(11).zip`**. The original Builder frontend/backend and old selector CSS, cards, physical finder and search are retained. No bidirectional sequence-to-property interface is used.

## Run locally (Windows VS Code / PowerShell)

From the extracted `ENCORE-Builder-main` directory:

```powershell
py scripts/preview_ui.py
```

Open `http://127.0.0.1:8080/selector/builder-filter.html` or `http://127.0.0.1:8080/selector/selector-alpha.html`. The UI preview runs without installing packages. Selecting an approved sequence opens the original Builder in step 1, **but its calculation API is not provided by this lightweight preview**.

To run the existing full application, install its normal Node / pnpm and Python dependencies and execute:

```powershell
corepack pnpm install
corepack pnpm dev
```

Then use the Nuxt dev URL printed by the server (usually `http://localhost:3000/`). Backend sequence and cloning calculations require the full dependencies, including `primer3` where applicable.

## Databank structure

- **Builder Filter** `/selector/builder-filter.html`: exactly 24 reviewed shell CDS designs. Original WT green / Engineered purple styles, T-number and diameter filters, one-click transfer to Builder. No provenance popups or transfer warnings.
- **Explore Encapsulins** `/selector/selector-alpha.html`: the original selector's `Search` and `Find a capsule` views. All 74 candidates and 51 assembly records (including non-exportable constructs) remain discoverable. **No transfer action to Builder.**

`unmodified` and `modified` compare the **shell protein** against the curated WT shell, not against a genetic DNA construct. Changes to symmetry, T-number, shell loading and cargo are *not* protein-sequence modifications. A modified shell has a concise change note taken from the curated assembly construct; if exact residues are not in the assembly record the description does not invent them. For some candidates no verified empty-shell reference exists; the previously curated reference is preserved. A consolidated architecture such as `Q1D6H4_T3` is treated as a WT protein-core record despite differences between specific published deposited chains; the new status does not assert that every experimental DNA construct is identical.

## Files and source-of-truth

- `encapsulin_selector/data/Open_Encapsulin_Databank.xlsx`: **the workbook from the uploaded original ZIP**, updated with assembly columns U–W and a 24-row `builder_catalog` sheet.
- `encapsulin_selector/data/assemblies/*.json`: assembly modification status, description, comparison reference, plus the existing curated measurements.
- `encapsulin_selector/data/builder_catalog.json`: approved CDS data (from the previously reviewed 24-design catalog; the sole intentional data supplement to the uploaded ZIP).
- `scripts/export-excel-to-json.py`: exports the original scientific sheets. Validate synchronization with `py scripts/export-excel-to-json.py --check` and update curated JSON with `--write`.
- `scripts/build-selector-data.mjs`: generates **both** `selector-data.js` and `builder-catalog.js`. Run `node scripts/build-selector-data.mjs` after exporting JSON.

The optional targeting-peptide features of the original Builder are untouched. No targeting-peptide selection was added to the filter.

## Scientific boundary

A shell's T-number or diameter is observed evidence, **not a promise** that transferring its coding sequence will produce precisely that architecture. `unmodified` also does **not** claim that experimental DNA matches the genomic reference. The 24 Builder designs have an explicitly curated passing translation check. Records without an approved CDS are still shown in Explore but not in Builder Filter.

## Update 16 October — Left-hand Builder Filter and localized sequence changes

Only two aspects of the classic GitLab-based interface were adjusted:

1. **Builder Filter** uses the same left-side filter panel pattern as the scientific finder. The approved catalog remains **24 unique shell CDS designs**, with T-number/diameter comparisons and direct transfer. Use **Clear filters** to restore all 24 options. On narrow screens, the panel moves above the results.
2. **Explore Encapsulins** shows the site of protein changes for each of the **20 modified assemblies**. Under the assembly heading, positions refer to the **1-based WT reference amino-acid sequence**, and red/green blocks show original/replacement residues when available. A red-only sequence denotes deletion; a green-only sequence denotes insertion. The full, scientifically curated description remains visible.

The columns added to `assemblies` in the Excel are:

- `shell_change_reference_positions_aa` — location in the WT reference protein
- `shell_change_original_aa` — reference residues shown in red (blank for an insertion or unverified residues)
- `shell_change_variant_aa` — replacement/inserted residues shown in green (blank for a deletion or unverified sequence)
- `shell_change_alignment_note` — basis, sequence caveat or numbering conflict

The locations derive from the curated protein sequences and annotations, **not** from guessing where mutation names fall. Notably, `Q1D6H4_pmut` maps to reference protein **I196–L203** while the published annotation calls it **ΔI195–L202**; both numbering conventions are disclosed rather than silently equated. `I6WZG6_His_T1_empty` has a C-terminal tag reported after the 265-residue shell, but the tag's exact amino-acid sequence is not established. Do not interpret the sequence comparison as proof of identity of the historical experimental plasmid.

To update both interface and source data after editing the workbook:

```powershell
py scripts/export-excel-to-json.py --write
node scripts/build-selector-data.mjs
py scripts/export-excel-to-json.py --check
node scripts/test-encore-simplified-ui.cjs
```

The targeting-peptide selection and full Builder calculation backend remain unchanged.

## Final Databank Overview and editable scientific audit workbook

The Databank now opens at `/selector/overview.html`: a short welcome, two guided paths, a searchable 20-term glossary, an EncA comparison and FAQs based on the approved six-page manual. This is editorial website content; it does not change the scientific JSON. The existing Builder Filter (24 approved CDS designs) and Explore Encapsulins (51 assembly records) keep their original behavior.

The production `encapsulin_selector/data/Open_Encapsulin_Databank.xlsx` is also supplied separately as `ENCORE_Databank_Final_Curation_Audit_16_10_2026.xlsx`. It contains the original ten science/documentation sheets **plus five editorial curation/audit sheets**: `CURATION_GUIDE`, `RELEASE_AUDIT`, `FIELD_GUIDE`, `OPEN_REVIEW_ISSUES` and `CURATION_LOG`. The new tabs do not enter the scientific JSON export.

For scientific edits, see `docs/CURATION_AND_AUDIT.md` and run:

```powershell
py scripts/export-excel-to-json.py --check
py scripts/export-excel-to-json.py --write
node scripts/build-selector-data.mjs
py scripts/export-excel-to-json.py --check
node scripts/test-encore-simplified-ui.cjs
py scripts/test-encore-overview.py
```

A first `--check` may deliberately report mismatches after workbook edits; it verifies whether exported JSON needs regeneration. Four existing pore-charge editorial fields remain unresolved and are documented in the workbook.


## Public dataset download (same workbook as curated source)

The Overview at `/selector/overview.html` now offers **Download scientific data (.xlsx)**. The link is
`/selector/data/Open_Encapsulin_Databank.xlsx`, directly serving the production workbook
`encapsulin_selector/data/Open_Encapsulin_Databank.xlsx`. No separate manually maintained public database is created.

The Excel includes a `PUBLIC_GUIDE` describing dataset scope, table relationships, interpretation caveats,
and known review issues, alongside scientific tables, citation mappings, curation guidance and audit logs.
A visitor may download it and examine all tables without access to the code. The file is independently
provided as `ENCORE_Databank_Public_Curation_16_10_2026.xlsx` in this release. The source file and the
public download must remain **byte-identical** for each release. Following a verified scientific change,
regenerate JSON and publish the updated workbook and static site together. Underlying papers should be cited.
