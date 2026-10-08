# commec-service

Optional sidecar container that makes [COMMEC](https://github.com/ibbis-bio/common-mechanism)
("Common Mechanism", IBBIS) usable over HTTP. commec itself is a
FASTA-in/JSON-out CLI without an API of its own; `app.py` is a thin wrapper
around it, so that `server/utils/commec.js` (in the main project) can call it
over HTTP.

Why a container of its own instead of part of the main image: commec needs
Conda and BLAST/HMMER, which is too heavy to install automatically like
primer3-py/ViennaRNA. Details and setup: see the section
"Biosecurity screening" in the [main README](../README.md).

## Database scope (important!)

On its first start the container downloads **only** the mandatory commec databases
(biorisk, control_lists, low_concern, best_match; ~6 GB download, ~40 GB on disk, via `commec setup -d /databases`, see
`entrypoint.sh`) into the volume `/databases`, **not** the full taxonomy databases (protein NR
~530 GB, nucleotide NT ~580 GB, together over 1 TB). Until the download is done `/health`
reports `ok: false` and the app shows the screening as off. The image uses commec 2.1.0 (the
version on the server; only available for x86_64, so the image is built for linux/amd64). That was a deliberate decision: the full databases do not fit
on the disk of most development machines and take very long to download.

Practical consequence: `commec screen` always runs here with `--skip-tx --skip-nt`
(`app.py`, controllable via `COMMEC_SKIP_TAXONOMY`). That way commec delivers
**no taxonomy best matches** against arbitrary organisms, only direct
sequence hits against the curated biorisk list (known toxins,
virulence factors, regulated pathogens). An important side effect: **every**
sequence without a hit gets `screen_status: "Warning"` from commec itself
with the rationale "Sequence risk is unknown, possibly generated in
silico.", even completely harmless genes such as GFP, because without the taxonomy check
nothing can be confirmed as *positively* safe. That is expected
commec behaviour with an incomplete database set, not an error.

That is why the frontend (`frontend/index.html`, `biosecEffectiveStatus()`)
evaluates the `biorisk` field in this case instead of the generic
`screen_status`: only a real biorisk hit (`biorisk` != `Pass`)
triggers the warning/block, not the general "unchecked" warning.

## Endpoints

- `GET /health`: `{"ok": bool, "detail": str}`. `ok` is `false` as long as
  `COMMEC_DB_DIR` (default `/databases`) is missing or empty.
- `POST /screen`: body `{"sequences": [{"label": str, "sequence": str}]}`,
  answer `{"results": [...]}` with one entry per input sequence, in
  the same order:
  - success: `{"available": true, "status": {"screen_status": "Pass"|"Warning"|"Flag"|"Mixed"|"Error"|"Skip", "biorisk": ..., "protein_taxonomy": ..., "nucleotide_taxonomy": ..., "low_concern": ..., "rationale": "..."}}`
    (the `status` object comes unchanged from commec itself)
  - failed (sequence too long, commec error, timeout, ...):
    `{"available": false, "reason": "..."}`

Every sequence runs as its own `commec screen` call in a temporary
directory (independent of each other; an error for one sequence does not block
the others in the same batch).

## Configuration (environment variables)

- `COMMEC_DB_DIR` (default `/databases`): where `commec setup` downloaded to.
- `COMMEC_THREADS` (default `4`): passed through to `commec screen -t`.
- `COMMEC_SKIP_TAXONOMY` (default `true` in `app.py`, `false` in `docker-compose.yml`): `true` appends `--skip-tx --skip-nt`
  (only the biorisk list is checked). With `commec setup` of commec 2.x the `best_match` databases come along, so the compose file
  switches the taxonomy steps on (measured here: 200 bp ~12 s, 2.7 kb ~17 s; with skip about half).
  Only set to `false` if this image has been extended with the protein/nucleotide taxonomy
  databases (see above).
- `COMMEC_RUN_TIMEOUT_SECONDS` (default `900`): hard timeout per
  single screen, so that a hanging sequence does not block the whole service.
- `COMMEC_MAX_SEQ_LEN` (default `20000`): sequences above this are rejected without
  a commec call with `available:false`.
- `PORT` (default `8787`).

## Verified

This wrapper was tested end to end against a real, locally built container
(commec 2.1.0, x86_64), not just built from the docs (the screening of a harmless GFP gene was run end to end after the
version change; a positive control with a real toxin sequence was not repeated with 2.1.0, only with 1.0.4):

- `commec setup -d /databases` (run by `entrypoint.sh`) downloads `biorisk/`, `control_lists/`, `low_concern/` and
  `best_match/` (~40 GB on disk), no taxonomy databases, and needs no input.
- `GET /health` reports `ok: true` as soon as the database is there.
- `POST /screen` with a harmless sequence (GFP) returns
  `biorisk: "Pass"` and `screen_status: "Pass (Skipped Taxonomy)"` (1.0.4 said `"Warning"`; the frontend only looks at the
  word in front of the bracket and, with skipped taxonomy, at `biorisk`).
- `POST /screen` with a real conotoxin sequence obtained from UniProt
  (Q9BPJ4, listed in the biorisk database as "Must flag") correctly returns
  `screen_status: "Flag"`, `biorisk: "Flag"`,
  `rationale: "Matches sequence with pathogenic or toxin function."`, and
  reliably triggers the blocking warning modal in the frontend.
