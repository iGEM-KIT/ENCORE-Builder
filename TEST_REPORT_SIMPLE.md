# Test Report — Original GitLab UI + Simple Databank (16 October 2026)

## Passed

- Original repository unpacked and retained as the primary application source.
- 74 candidates, 51 assemblies, 56 pores and 131 evidence rows preserved from the uploaded project.
- 24 unique, translation-QC `PASS` designs from the curated Builder catalog; each has an exact-length ACGT CDS, a valid candidate and an existing assembly.
- Excel ↔ JSON exporter `--check`: 390 unchanged export targets, no new/missing/different JSON files.
- Existing Node/server unit tests plus new Builder Filter logic tests: **21 passed**.
- Browser DOM-rendering test (Chromium, static injection) for old selector and new Builder Filter: no JavaScript page errors; the Builder Filter displayed 24 entries.
- Letter11 matched both T=3 and T=4 requirements while remaining one selectable CDS.
- 3×His tetrahedral assembly retained `T=N/A` rather than being mislabeled T=1.
- Browser filtering with pore-observation and family criteria passed.
- JavaScript handoff test checked exact Letter11 816-nt CDS, its design ID and absence of a transfer-warning property.
- Explore has no action or event handler to transfer any of its unvalidated reference sequences to Builder.
- The original Nuxt Builder frontend/back-end source files were not rewritten, apart from the Databank link in the header and intro.

## Limitations

- Direct Chromium navigation to local HTTP URLs was blocked by this execution environment. Browser pages were instead rendered from their same HTML/CSS/JS content and the local Python HTTP server was checked separately.
- The complete Nuxt + Biologik/primer3 computation workflow was not exercised. `python -m pytest` stops during collection because `primer3` is absent in this environment.
- Four pre-existing unresolved pore-editor charge notes remain in the original Excel; exporter preserves them as null JSON values. No scientific guesses were made.
- Labels `modified` and `unmodified` describe the documented shell protein relative to the curated reference. They are **not a verified genetic alignment for every experimental construct**. The assembly source documentation remains authoritative.
