# Encapsulin database for the selector

Every encapsulin is a JSON file of its own. To add a new candidate,
NO knowledge of the rest of the codebase is needed,
just these three steps:

1. Copy `candidates/_template.json` to `candidates/<YOUR_ID>.json`
   (e.g. the UniProt accession, as for all existing entries: `Q1D6H4.json`).
2. Fill in the fields. Simply leave unknown fields as `null`; the
   existing 74 entries do that in many places too.
3. Optional: add one or more measured assemblies in `assemblies/`
   (see below), then set `reference_assembly_id` in the candidate file to the
   most important of them.

Then start `pnpm dev` (rebuilds `selector-data.js` automatically) and check in the
filter at `/selector/` whether the new entry shows up. In a
pull request, commit the newly built `encapsulin_selector/selector-data.js` as well
(if forgotten, a maintainer adds it with
`pnpm build:selector-data`).

**Never edit `selector-data.js` itself by hand.** The file is generated from
this folder (see `scripts/build-selector-data.mjs`) and is overwritten at the
next build.

## candidates/<ID>.json

One entry per protein/UniProt entry. Used directly for search/filter in the
selector: `candidate_id`, `entry_name`, `protein_name`, `organism`,
`genus`, `strain`, `gene`, `locus_tag`, `orf_name`, `encapsulin_family`,
`reference_assembly_id`. `source_uniprot` is shown as a link behind the
`candidate_id` in the candidate card if set; with a
real UniProt accession as `candidate_id`, just enter
`https://www.uniprot.org/uniprotkb/<candidate_id>/entry`. The rest
is curation metadata (sources, confidence level, notes), useful
but optional/`null` if unknown.

`assembly_count` does NOT belong in this file; the build step counts it
automatically from the matching files in `assemblies/`.

## assemblies/<ID>.json

A measured/observed capsid variant (e.g. a specific T number state)
of a candidate, linked through `candidate_id`. A candidate can have several
assemblies (e.g. T=1 and T=3). `shell_diameter_nm` may be a number
(`24`), an approximate value (`"~24"`) or a range (`"20-24"`); the
build step automatically converts it into the internally used min/max/center form,
so nothing more has to be filled in here.

An assembly has NO UniProt entry of its own (UniProt indexes
protein sequences, not individual experimental structures or mutants);
instead `structure_id` is shown as a link to the matching RCSB PDB page
if set. Separate several PDB codes with a semicolon
(`"4PT2; 7S20"`), each is linked individually.

## meta.json

General description of the database (title, source, hint texts). The
counters (`candidate_count`, `assembly_count`, ...) do not belong here,
the build step computes them itself.

## Validation

`pnpm build:selector-data` aborts with a clear error message if:

- a `candidate_id`/`assembly_id` was assigned twice,
- an assembly refers to a non-existent `candidate_id`,
- a candidate with `reference_assembly_id` refers to a non-existent
  assembly.
