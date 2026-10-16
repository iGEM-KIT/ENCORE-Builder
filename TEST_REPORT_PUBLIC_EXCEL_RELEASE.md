# Public Excel release integration — 16 October 2026

## Role of workbook

The site and the standalone public Excel are the **same scientific source file**; no split public/private Databank is maintained. The production workbook is at `encapsulin_selector/data/Open_Encapsulin_Databank.xlsx`, reachable through the Overview download link `/selector/data/Open_Encapsulin_Databank.xlsx`. A new `PUBLIC_GUIDE` documents user-facing meanings, incomplete annotations, citations and the curator workflow.

## Automated checks

- `python scripts/export-excel-to-json.py --check`: validated 74 candidates, 51 assemblies, 56 pores, 131 evidence records, and 24 approved Builder CDS; **390 unchanged, 0 new, 0 different**.
- `node scripts/test-encore-simplified-ui.cjs`: passed, including Builder transfer and mutation comparison.
- `python scripts/test-encore-overview.py`: passed, including navigation, glossary and tutorial anchors.
- Local HTTP GET on Overview and `.xlsx` path: checked successfully as part of packaging.
- Byte equality between standalone public `.xlsx` and the workbook included in the ZIP: verified by SHA-256.

## Outstanding

Four pore-charge annotations remain unresolved in `OPEN_REVIEW_ISSUES` and remain blank/null in public data. Scientific review and Builder calculation backend were not revalidated in this edit. No copyright/reuse license has been assigned by this release.
