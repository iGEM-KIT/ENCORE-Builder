# ENCORE 16 October 2026 — data curation and release audit

## Authoritative production workbook

`encapsulin_selector/data/Open_Encapsulin_Databank.xlsx` is the **same workbook** provided separately as `ENCORE_Databank_Final_Curation_Audit_16_10_2026.xlsx`. This file is the input to `scripts/export-excel-to-json.py`.

This release has **74 candidates, 51 assemblies, 56 pore records, 74 genomic sequence links, 139 evidence entries, 181 citation links, 47 DOI index entries, 19 targeting-peptide records, 50 targeting-peptide to assembly links, and 24 approved Builder designs**. These are the counts of the JSON files on 19 October 2026. The baseline of the release on 16 October was 131 evidence entries, 154 citation links and 46 DOI index entries, so the sheet `RELEASE_AUDIT` can still show the older numbers. The release sheet `RELEASE_AUDIT` records these *baseline* counts with live Excel formulas. Baseline matching alone does **not** validate scientific correctness; the exporter provides stronger schema and data synchronization checks.

### Source tabs

| Tab | Responsibility | Used in site |
| --- | --- | --- |
| databank | Candidate identity, UniProt, taxonomy, reference assembly | Explore the data |
| assemblies | Symmetry, T-number, diameter, shell change, positions and source | Explore the data; assembly comparison in Choose a shell |
| pores | Observations of individual pores; states, charge, method, structure | Explore the data (pore filters) |
| sequence_links | Genomic reference sequence (distinct from the Builder CDS) | Explore the data |
| evidence | Experimental value, support method and source | Explore the data |
| citation_links, doi_index | Source mapping, paper and PDB links | Explore the data |
| vocabularies | Scientific categories and filter values | Both filtering modes |
| builder_catalog | **24 vetted CDS designs**, unique sequence IDs, translation check | Choose a shell → Builder |

### Editorial/audit tabs (not exported as JSON)

- `CURATION_GUIDE`: step-by-step curator process and commands.
- `RELEASE_AUDIT`: dynamic row counts compared with the release snapshot.
- `FIELD_GUIDE`: meanings and constraints for particularly critical fields.
- `OPEN_REVIEW_ISSUES`: four genuine unresolved `pores.charge_exterior` editor annotations.
- `CURATION_LOG`: blank change log for changes to individual records.

The workbook retains its original `README` tab and scientific fields. A new Overview website page is **editorial guidance**, not a new data schema, and its glossary is not duplicated into the scientific tables.

### Shell-modification protocol

Modify `assemblies` columns **U:AA** after comparing the shell *protein* to the WT reference. `shell_sequence_status` is `unmodified` or `modified` only when supported by the evidence. Specify reference assembly, residue positions, original amino acids, new amino acids and any numbering conflicts. Red denotes original residues; green denotes replacement/insertion; architecture or cargo changes alone are **not** protein mutations. If residues are not reported, keep them unknown.

### Builder eligibility protocol

The Choose a shell contains only approved `builder_catalog` rows. Do **not** infer a CDS from a protein sequence or approve a sequence without an appropriate translation check. A reported T-number/diameter is context for shell selection; it is not guaranteed by transfer of a CDS.

### Update the site after curating the Excel

Use PowerShell inside `ENCORE-Builder-main`:

```powershell
py scripts/export-excel-to-json.py --check
py scripts/export-excel-to-json.py --write
node scripts/build-selector-data.mjs
py scripts/export-excel-to-json.py --check
node scripts/test-encore-simplified-ui.cjs
```

The first `--check` can **fail** after a valid spreadsheet edit because JSON files are not yet synchronized; inspect what changed, then use `--write` and rerun `--check`. The exporter intentionally refuses to silently delete records. Commit the modified workbook alongside generated JSON and JS.

### Known audit warnings, not silently 'fixed'

Four `pores.charge_exterior` cells (Excel rows 9–12) contain editorial placeholders. Exporter warns and currently publishes those fields as null; the curator must check the original papers to resolve them. They do **not** prevent the current selector from functioning.

### Reproduction of final release

```powershell
py scripts/preview_ui.py
```

Open `http://127.0.0.1:8080/selector/overview.html` for the static preview. This preview does **not** start the Builder's computation services. `pnpm dev` and the full backend dependencies are needed to validate calculations; the Overview, Choose a shell and Explore interfaces can be reviewed without them.
