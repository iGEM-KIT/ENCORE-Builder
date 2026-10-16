# ENCORE Overview / Excel release — test report, 16 October 2026

**Source:** last GitLab-classic ZIP (`ENCORE_GitLab_Filtro_Esquerda_Mutacoes_Posicoes_16_10_2026.zip`). The two filters and Builder implementation are retained. No bidirectional sequence explorer was reintroduced.

## Verified
- Static Overview integration: `overview.html`, `overview.css`, three Databank navigation tabs, Builder homepage `Databank` link, guide link.
- Manual content: welcome, Builder Filter workflow, Explore workflow, 20 scientific glossary entries, EncA modification example, T-number and tetrahedral clarification, common questions.
- `scripts/test-encore-overview.py`: passed; link presence, glossary count, guide anchors and nav.
- `scripts/test-encore-simplified-ui.cjs`: passed; 24 Builder CDS designs, left sidebar, filters, direct CDS transfer, four scientific sequence examples.
- `scripts/export-excel-to-json.py --check`: passed; **390 unchanged, 0 different, 0 new, 0 unexpected** generated JSON files.
- Production workbook: 10 original sheets + 5 audit/curation sheets. RELEASE_AUDIT formulas produce expected counts, spreadsheet formula-error scan returned zero matches.
- Local Python preview server: `GET /selector/overview.html` returned HTTP 200 on free test port.

## Existing manual review items
- `pores!K9:K12` (four editor placeholders in `charge_exterior`) are exported as null. These existed before this integration and are listed in `OPEN_REVIEW_ISSUES`.

## Not fully verified here
- Automated visual browser review: Chromium browser was blocked from opening even local HTTP pages by the environment (`ERR_BLOCKED_BY_ADMINISTRATOR`). CSS and HTML were tested statically; visual confirmation on Windows is still recommended.
- Full Builder computational/backend dependency environment was not started; the Builder code itself was not changed in this release.

## Windows preview

```powershell
py scripts/preview_ui.py
```

Open `http://localhost:8080/selector/overview.html` and review Welcome / How to use / Glossary, then both filters. The static preview does not execute backend design calculations.
