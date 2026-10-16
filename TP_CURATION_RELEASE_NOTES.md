# ENCORE Open Database — targeting peptides (TPs) in the public Excel only

**Release basis:** `ENCORE_Open_Database_Community_Contributions_Placeholder_16_10_2026.zip`.

**Authoritative workbook:** `encapsulin_selector/data/Open_Encapsulin_Databank.xlsx` (also the file served by the Overview download button).

## What changed

- Added one Excel worksheet named **`targeting_peptides`** with **22 records** from `ENCORE_targeting_peptides_16_10_2026.xlsx`.
- Original TP columns **A–W** were copied as curated source data. Audit columns **X–AF** were also copied, including their *live Excel formulas* in X and Y and all suggested actions.
- The existing public workbook scientific sheets, shell sequences, assemblies, pores, citations and the catalog of **24 shell CDS choices** have not been scientifically revised.
- Added explanatory rows to workbook tabs `README`, `PUBLIC_GUIDE`, `CURATION_GUIDE` and a count in `RELEASE_AUDIT`.

## Deliberate release boundary

The `targeting_peptides` tab is a **public curation/research table**, **not** an enabled selection feature.

- **Explore Encapsulins** does not display or select TPs.
- **Builder Filter** continues to display **only the 24 approved shell CDS designs**; TPs are not added to its options.
- `scripts/export-excel-to-json.py` continues to whitelist shell-related sheets; it deliberately ignores `targeting_peptides`.
- The project's existing toolkit source files (`tp-TP-Mx.json`, `tp-TP-Qt.json`, `tp-TP-Tm.json`) were **not altered**. These older code files are not being validated or promoted by this Excel extension.

The TP data remain under scientific review: the source workbook marks 10 records `verified` and 12 `review_required`, and proposes actions in 7 rows. This does **not** mean that 10 TPs are independently validated for arbitrary Builder use. The `Q9WZP2_TOOLKIT_TM` DNA conflict was retained as a review issue; no unconfirmed correction was applied.

## Updating this release

1. Update `encapsulin_selector/data/Open_Encapsulin_Databank.xlsx` in Excel.
2. Preserve primary keys, source DOIs, sequences, TP review statuses and audit columns.
3. Run `py scripts/export-excel-to-json.py --check` to verify the shell-related JSON remains synchronized.
4. Run `py scripts/test-tp-curation-only.py` to check the TP-only export boundary.
5. If shell-related science changed, regenerate the shell JSON with `py scripts/export-excel-to-json.py --write` and the compiled selector with `node scripts/build-selector-data.mjs` only after review. Do **not** add TP exports by accident.

The `README` and `PUBLIC_GUIDE` sheets explain the Excel data model to public users.
