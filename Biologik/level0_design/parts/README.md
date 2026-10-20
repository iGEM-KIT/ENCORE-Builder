# Sequence database for Golden Gate standard parts

Every entry is a JSON file of its own, grouped by kind in a subfolder, exactly like
`encapsulin_selector/data/` for the encapsulins. A new or changed file takes effect immediately (no build, no restart):
`cli.py` is restarted per request and reads the files fresh from disk every time.

| Folder              | Content |
|---------------------|---------|
| `level0_inserts/`   | the bare part sequence of each Level 0 plasmid: shells, cargos, linkers, markers, intein, targeting peptides, NCS (see below) |
| `promoters/`        | bidirectional promoters, all with a real sequence: GAL1-10 (665 bp), BDP306 (754 bp), BDP565 (356 bp), BDP670 (318 bp). A file is a dropdown entry: `label`, `desc`, `order`, `sequence` (sense direction of the nanocompartment module, free of BsaI/BbsI sites). A promoter without a sequence is not offered. The Builder also takes an own promoter (`promoter: "custom"`, `customPromoter`), see `sequence.validate_promoter` and `primers.design_promoter_primers` |
| `terminators/`      | terminators, purely informational |
| `level0_backbones/`, `level1_backbones/`, `level2_backbones/` | the destination backbones pAGM9121, pAGM1311, pESC-HIS |
| `type_overhangs/`   | the seven overhang adapters (source of the overhangs and the frame spacer) |

The frame spacer is GC in every adapter, although the lab plasmids carry AT or TA at these two positions. This is a decision, not an
oversight. The two spacer bases sit in one codon together with one neighbouring base (which one depends on the strand a module is
read on, the cargo module is read on the antisense strand). With AT that codon can become ATG, with TA it can become TAA or TAG, so a
start or stop codon can arise at a junction. GC cannot form any start or stop codon. An empirical check supports it: with TA in all
spacers the cargo ORF got a premature stop codon in 84 of 120 test designs. The price of GC is that the amino acid at a junction can
differ from the lab plasmid. In the comparison with the cloned reference construct (Level 2, *Q. thermotolerans* shell, LGB4, SpyTag,
3×GSSS, SpyCatcher) this was the only difference, four bases of the frame spacers.

The dropdowns of the software (catalogue metadata such as labels, T number, description) live in `data.py`; which parts really exist at
which site and slot and what sequence they have comes from `level0_inserts/`.

## `level0_inserts/<category>-<part>.json`

One file per PART (not per plasmid), e.g. `shell-E-Tm.json`, `linker-GSSS3.json`, `tp-TP-Mx.json`; all NCS spacers together in
`ncs.json`. The part sequence is stored ONCE in `sequence`, plus the list of the Level 0 plasmids that carry it in `plasmids`.
`parts_db.inserts()` expands every file into one entry per plasmid (part fields + plasmid fields), so the rest of the software
still sees one entry per Level 0 plasmid (`id` = plasmid id, e.g. `Lvl0.2_b_034`).

`sequence` is the BARE part: sense strand (as it is read; a part that lies in the plasmid as a reverse complement, cargo site, has
already been turned back here), **without start codon, without stop codon, without overhangs and without the frame spacer**.
The software adds ATG and the stop codon per slot when it builds the construct (`constructs._orf_flags`, `_add_start_stop`):
the first coding part of an ORF gets ATG, the last one a stop codon (TAA), wherever it sits; the NC module
is read Type 0.1 -> 0.5, the cargo module Type 0.5 -> 0.1; the central part (0.3) is coding too, so it gets the stop codon when every
part behind it is an NCS spacer. So one sequence serves every slot (a targeting peptide at Type 0.5 gets ATG, at Type 0.1 a stop codon). Overhangs and the frame spacer come from `type_overhangs/`.
Own sequences of the user are treated the same way, but an ATG or stop codon they already carry is not doubled.
Linkers and NCS spacers are stored as they are (no start/stop logic for NCS; linkers carry none). Every Type has its own NCS sequence (iGEM Registry Dummy Parts [0.1], [0.2], [0.4], [0.5]; stored per plasmid in `ncs.json`); the combined spacers 0.12 and 0.45 use the sequence of Type 0.1 and Type 0.4. There is no NCS with stop codon.

Part fields: `id`, `category` (`shell`, `cargo`, `linker`, `marker`, `intein`, `tp`, `ncs`), `part` / `part_label` (part id and label
in the dropdowns, e.g. linker `GSSS3`), `sequence`,
`sequence_status`, `length_bp`, `checks` (length divisible by 3, BsaI/BbsI sites in the part), `organism`, `source`, `notes`, `used_by`.

Plasmid fields (`plasmids` list):

- `id`, `label`, `plasmid_name`: internal id (`null` if not built), name in the Level 0 constructs table and name in the GenBank file.
- `type_slot` (1-5) and `site` (`nc_site` / `cargo_site`). For Type 0.1/0.5 the site follows from the Level 2 overhang
  (`level2_overhang`: TGAT/AATG = NC site, CCAA/CGTT = cargo site), for Type 0.2-0.4 from the strand on which the part lies in the
  plasmid (`stored_orientation`: sense = NC site, antisense = cargo site; the "rc" plasmids).
- `frame_spacer_in_plasmid`: the 2 bases the plasmid carries before the ORF (only for traceability).
- A plasmid entry whose internal `id` is set counts as built; one with `id: null` is only planned and is shown as "(not built)".
- `registry_url`: link to the part in the iGEM Registry, `null` until it is known. The builder shows it for every toolbox part in the order lists of step 5 (a placeholder while it is `null`).
- `notes`: oddities noticed during the import (to be checked).
- `covers_slots` (combined NCS only, e.g. `0.12 NCS` = `[1, 2]`, `0.45 NCS` = `[4, 5]`): the spacer covers two slots at once; `type_slot` is then
  `null`. The builder offers them as "NCS 0.12" / "NCS 0.45" in both slots they cover: choosing one sets and locks the other slot, and the
  result is ONE Level 0 part (Type 0.12 / 0.45) with its own adapter (`type_overhangs/0.12`, `0.12rc`, `0.45`, `0.45rc`: the left of the first
  and the right of the second adapter, without the overhang in between) and one Level 1 fragment fewer.

Plasmids with `id: null` are listed in `Level 0 constructs.xlsx` (id "-") but are not built and not in the lab system; they are in the database
only for completeness and so that the part can be chosen at that slot. They have no internal id and `registry_url` is `null`.
The site of a plasmid follows the table where it disagreed with the GenBank orientation (L1 linkers at 0.2/0.4, MVP).

To add a plasmid of an existing part (e.g. the same linker at another slot): append an entry to its `plasmids` list. To add a new
part: copy `_template.json`. A part can be used at any slot (the sequence of the same part from another slot is used then, without a
plasmid entry of its own, so without a registry link); the dropdowns only offer a part where a plasmid exists (`slots` per library
in `get_libraries()`).

## Common fields (promoters/, terminators/)

- `id`, `kind`, `label`, `sequence` (or `null`), `sequence_status` (`real`/`missing`), `length_bp`,
  `organism`, `source`, `notes`, `used_by`.

## `level0_backbones/`, `level1_backbones/`, `level2_backbones/<id>.json`

A complete, circular plasmid backbone (e.g. imported from a GenBank file)
with the full sequence, the curated core fields (marker, origin,
acceptor overhangs `receiver_overhangs.5_prime`/`3_prime`, currently occupying
stuffer/test cassette in `current_insert`) AND the complete, raw
parsed GenBank `FEATURES` table (`features`: list of
`{type, location, qualifiers}`) for maximum traceability. 

Currently stored as real: `pAGM9121-lvl0-dest` (Level 0, MoClo plasmid family: Weber et al. 2011 and Werner et al. 2012 describe the system, but Weber et al. 2011 does not name this plasmid),
`pAGM1311-lvl1-dest` (Level 1, MoClo plasmid family, see the `source` field), `pESC-HIS-lvl2-dest`
(Level 2, pESC-HIS adapted from Yuan et al. 2021, provided by the user). All three come from GenBank files
provided by the user, not generated by ourselves.

## `type_overhangs/<id>.json`

The seven overhang adapters that are attached to the sequence of every Level 0 part
(BbsI cut site, Level 0 overhangs 0N/0C matching the Level 0 backbone, Level 1 overhangs
for the respective Type slot and, for Type 0.1/0.5, additionally the Level 2 overhangs, around a
4-nt "insert" placeholder). The CDS or part sequence replaces this placeholder. One
file per adapter, file name = `id` = name in the user's GenBank file:

| id      | Type slot | `used_for_modules`        | Special feature |
|---------|-----------|---------------------------|-----------------|
| `0.1`   | 0.1       | `nc_site`                 | Level 2 overhang `2_N` = TGAT |
| `0.1rc` | 0.1       | `cargo_site`              | Level 2 overhang `2_N` = CCAA (cargo module, rc variant) |
| `0.2`   | 0.2       | `nc_site`, `cargo_site`   | both sides |
| `0.3`   | 0.3       | `nc_site`, `cargo_site`   | both sides |
| `0.4`   | 0.4       | `nc_site`, `cargo_site`   | both sides |
| `0.5`   | 0.5       | `nc_site`                 | Level 2 overhang `2_C` = AATG |
| `0.5rc` | 0.5       | `cargo_site`              | Level 2 overhang `2_C` = CGTT (cargo module, rc variant) |

Fields (in addition to `id`/`kind`/`label`/`sequence`/`sequence_status`/
`length_bp`/`source`/`notes`/`used_by`, see above):

- `type_slot`: 1..5 (Type 0.x).
- `used_for_modules`: list of `"nc_site"` (nanocompartment site) and/or `"cargo_site"`.
- `reverse_complement_variant`: `true` for the `rc` adapters of the cargo site (antisense module).
- `description`: DEFINITION line from the GenBank file.
- `enzyme`, `bbsi_sites`: recognition sites (`GAAGAC` or rc) with position/strand.
- `overhangs`: list of the labelled overhangs: `label` (e.g. `0.5N Lvl1`), `role`
  (`level0_N`, `level1_N`, `level2_N`, `level1_C`, `level2_C`, `level0_C`), `location`, `strand`,
  `sequence_top_strand` (bases on the top strand) and `sequence_own_strand_5to3` (as read on
  its own strand, so for `strand: "-"` the reverse complement).
- `insert`: position and placeholder (`AAAA`) of the place where the CDS is inserted.
- `frame_spacer`: 2 nt (`GC`) directly before the insert (5' side, top strand), behind the Level 1 N overhang and thus
  INSIDE the BsaI fragment (it is not cut out during cloning). The 4-nt overhang between two parts
  alone shifts the reading frame by 1 nt; overhang (4) + spacer (2) = 6 nt = two codons, fused parts stay in
  frame. Chosen so that in both reading directions (sense and cargo module, which lies antisense) no stop codon arises at
  the seam and no BsaI/BbsI site is newly formed (test: `test_junction_codons_are_never_stops_...`).
- `features`: the complete, raw parsed GenBank feature table.

Status: the overhangs of the adapters were checked against the earlier hard-coded constants (Level 1 overhangs
per slot, NC flanks TGAT/TTAC, cargo flanks CCAA/GCAA, the right value each as a complement); the adapters are now
the source for them. Not covered: the promoter flank ACTA.

## Validation

`load_parts()` (`parts_db.py`) aborts with a clear error message (instead of
silently loading a broken database) if an `id` is missing in a folder
or assigned twice, or a file is not valid JSON.
