# TODO — Community contributions to the Open Database

**Status:** Planned, not yet implemented. The Overview includes a clearly marked placeholder. No online submission endpoint, review queue or automatic Excel updates exist in this version.

## Intended visitor experience

A future submission workflow should let external researchers propose:

- a new encapsulin candidate (organism, identifier and shell protein information);
- a new assembly/architecture or a new experimental state of an existing shell;
- an engineered variant with substitutions, insertions, deletions or tags and their positions relative to a stated reference;
- new pore/physical-property observations, experimental conditions or sources;
- a correction to a record already in the database.

## Minimum submission information to define

- Record type and related existing candidate/assembly IDs (if applicable).
- Source publication (DOI or direct reference), structure ID (PDB) where available, and measurement methods/conditions.
- Protein sequence and, where relevant and actually available, a CDS; sequence modifications must specify reference and positions.
- Contributor identification/attribution and consent/license terms (to be determined).
- Evidence confidence and rules for missing/not-reported fields.

## Integration tasks before launch

1. Choose contribution channel: submission form, email, GitLab issue/MR, or another moderated workflow. **PLACEHOLDER — decide public form/contact URL.**
2. Define scientific validation, duplicate handling and reference/provenance checks. **PLACEHOLDER — assign curator/reviewer and criteria.**
3. Agree on reuse license, privacy and attribution policy. **PLACEHOLDER — add approved terms.**
4. Ensure approved changes enter the **single authoritative public Excel workbook**, then regenerate site JSON using the existing export pipeline.
5. Update Overview: replace disabled button with an active accessible link only when the endpoint and review workflow work, and remove the "coming soon" label.
6. Consider a contextual "Suggest a correction" link in Explore Encapsulins only after the same submission workflow is ready. **PLACEHOLDER — not implemented.**

**Scientific principle:** A community suggestion is not a validated experimental result. It must not appear as verified data or automatically become Builder-eligible without curation and an approved CDS.
