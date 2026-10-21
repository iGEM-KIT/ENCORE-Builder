# Developer guide

This guide is for people who want to read, change or extend the ENCORE-Builder. How to install and use the
program is explained in the [README](../README.md).

Contents: [How it is built](#how-it-is-built), [Local development](#local-development-without-docker),
[Calling the Builder from a script](#calling-the-builder-from-a-script), [Reproduce the example without the web page](#reproduce-the-example-without-the-web-page),
[Adding a part](#adding-a-part), [Publishing the Docker images](#publishing-the-docker-images),
[Running the tests](#running-the-tests), [GitHub and GitLab](#github-and-gitlab),
[Biosecurity screening (COMMEC): details](#biosecurity-screening-commec-details),
[Extending the Open NC Database](#extending-the-open-nc-database).

## How it is built

A picture of the parts and the data flow is in [docs/ARCHITECTURE.md](ARCHITECTURE.md).
The HTTP interface is described in [docs/openapi.yaml](openapi.yaml) (OpenAPI 3), so that
other tools can call the Builder.

## Local development (without Docker)

Requirements: Node.js ≥20.19 and [pnpm](https://pnpm.io/).

```bash
pnpm install
pnpm dev
```

On the first start `pnpm dev` automatically creates a `.venv` with primer3-py
([scripts/setup-python.mjs](../scripts/setup-python.mjs)), so no manual
`pip install` is needed. If there is no Python 3 on the PATH or the installation
fails (e.g. missing C compiler), Biologik keeps running anyway, only with
a less accurate Wallace Tm estimate instead of primer3. A specific
interpreter can be forced with `BIOLOGIK_PYTHON=/path/to/python`.

The main image alone (`docker build -t encore-builder .`, ENCORE-Builder and Open NC Database) starts without the screening container,
but then it does not calculate any construct. Users should always start the Compose files so that the
screening is included.

## Calling the Builder from a script

The Builder has a small HTTP interface, described in [docs/openapi.yaml](openapi.yaml). With the
software running on port 3000 (started with Docker Desktop as described in the README, or with `pnpm dev`), a design of the example from the README looks like this:

```bash
curl -X POST http://localhost:3000/api/design \
  -H "content-type: application/json" \
  -d @docs/examples/oxygen-free-space-request.json
```

or from Python, with the standard library only:

```python
import json
import urllib.request

with open("docs/examples/oxygen-free-space-request.json") as f:
    request = json.load(f)
req = urllib.request.Request(
    "http://localhost:3000/api/design",
    data=json.dumps(request).encode(),
    headers={"content-type": "application/json"},
)
design = json.load(urllib.request.urlopen(req))

print(design["level2Construct"]["length"], "bp insert")           # 2555 bp insert
for primer in design["primers"]:
    print(primer["name"], primer["full"])
```

`GET /api/libraries` lists the ids that you can use (shells, cargos, linkers, markers, promoters).
A request that cannot be calculated gets the status 400 and a message that says why. Add
`"genbank": true` to the request to get a GenBank file in the field `genbank` of the answer.
The Builder pages offer every download as GenBank or as SBOL 3 (Turtle, `.ttl`). The SBOL 3 file is made in the
browser from the same GenBank text by [frontend/sbol.js](../frontend/sbol.js), so the API and the command line return GenBank only.
The same calculation runs without the web server:
`python3 -m Biologik.level0_design.cli design < request.json`.

## Reproduce the example without the web page

The example of the README ("Reproduce the example") also runs without the web server. It needs Python 3 and the
packages of `Biologik/requirements.txt`. From the project folder:

```bash
python3 -m Biologik.level0_design.cli design < docs/examples/oxygen-free-space-request.json
```

The request is the file [examples/oxygen-free-space-request.json](examples/oxygen-free-space-request.json).
The expected numbers are in the table of the README, and the test
[tests/unit/biologik/test_reference_example.py](../tests/unit/biologik/test_reference_example.py) checks them on every push.

## Adding a part

The part files are plain JSON in
[Biologik/level0_design/parts/](../Biologik/level0_design/parts/README.md). No build and no restart is needed, the
engine reads them fresh for every request.

1. Copy `Biologik/level0_design/parts/level0_inserts/_template.json` to `<category>-<part>.json`
   (for example `cargo-myprotein.json`).
2. Fill in the fields. `sequence` is the bare part: sense strand, **without** start codon, stop codon,
   overhangs and frame spacer, a multiple of 3 and free of BsaI and BbsI sites. The Builder adds ATG
   and the stop codon where they are needed. `plasmids` lists the Level 0 plasmids that carry the part
   (Type slot and site).
3. What else depends on the kind of part:

| Kind of part | Also needed |
|---|---|
| Cargo | nothing, it appears in the cargo list by itself |
| Linker or surface marker | one line (id, label, description) in `_LINKER_META` or `_MARKER_META` in `Biologik/level0_design/data.py` |
| Shell (nanocompartment) | one line in `NANOCOMPARTMENTS` in `data.py`, plus the file of its targeting peptide (`tp-...`) |
| Promoter | a file in `Biologik/level0_design/parts/promoters/` with `label`, `desc`, `order` and `sequence` |

4. Check it: `GET /api/libraries` must list the part, then run `python3 -m pytest -q`. The tests check
   that every coding part is a multiple of 3 and that the finished constructs carry no BsaI or BbsI site.

For a new encapsulin in the Open NC Database see
[encapsulin_selector/data/README.md](../encapsulin_selector/data/README.md).

## Publishing the Docker images

The workflow [.github/workflows/publish-images.yml](../.github/workflows/publish-images.yml)
builds both images for `linux/amd64` and `linux/arm64` and pushes them to Docker Hub and to the GitHub Container
Registry on every push to `main`, on version tags (`v1.2.3`) and by hand from the Actions tab:

* `igemkit/encore-builder` (ENCORE-Builder and Open NC Database)
* `igemkit/encore-builder-commec` (biosecurity screening)

Both are also published as `ghcr.io/igem-kit/...`. The workflow needs the repository secrets
`DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` (a Docker Hub access token with Read & Write permission).

`docker-compose.yml` has both `image:` and `build:` for every service, so
`docker compose up --build` builds both images from the source code (10 to 30 minutes) and plain
`docker compose up` pulls them from Docker Hub; `docker-compose.pull.yml` is the image-only variant for users who prefer the terminal.

## Running the tests

```bash
pip install pytest -r Biologik/requirements.txt   # once (primer3-py is needed for the primer tests)
pnpm test                                          # Node tests, then Python tests
# or separately:
pnpm test:node                                     # Node tests: server bridges, selector filters, translations
pnpm test:py                                       # python3 -m pytest (tests/unit)
```

What is covered:

* `tests/unit/biologik/`: the design engine (cargo validation, codon optimization, slots, combined NCS, Level 0 to 2
  assembly, primers, oligos, GenBank) and the primer design (Tm balancing, dimers, extensions).
* `tests/unit/commec_service/`: the HTTP wrapper of the screening container, with COMMEC itself replaced.
* `tests/unit/data/`: integrity of the nanocompartment database (references between candidates, assemblies, pores and
  citations), that `selector-data.js` is up to date, and the file rules of the parts database.
* `tests/unit/frontend/`: the pages are well formed, internal links and looked-up ids exist, and the house rules for visible
  text hold (no dashes as punctuation).
* `tests/unit/selector/`: the filters and the hand-off from the Open NC Database to the Builder.
* `tests/unit/frontend/i18n.test.mjs`: the translation engine (exact texts, texts with values, right-to-left for Arabic,
  fallback to English).
* `tests/unit/server/`: the bridge to the Python engine and the bridge to the screening container (it must never turn
  a missing screening into an error).

The workflow [.github/workflows/tests.yml](../.github/workflows/tests.yml) runs everything on every push to `main` and on every
pull request. The interactive parts of the pages (clicking through the steps) are not covered by an automated test yet.

## GitHub and GitLab

The project is published on GitHub (team repository, where the Docker images and the automatic tests are built) and on the
GitLab of the iGEM competition. The two repositories have the same files but different histories (GitLab also holds a few files
of the iGEM template), so a normal push to GitLab is rejected and a force push would destroy its history. Instead,
[scripts/sync-gitlab.sh](../scripts/sync-gitlab.sh) copies the changes since the last synced GitHub commit onto the GitLab `main` as one new commit:

```bash
git remote add gitlab https://gitlab.igem.org/2026/software/kit/encore-software.git   # once
scripts/sync-gitlab.sh <last-synced-github-commit> "<commit message>"
```

The tests also run on GitLab: [.gitlab-ci.yml](../.gitlab-ci.yml) has the same two jobs (Python and Node) as the GitHub workflow
[tests.yml](../.github/workflows/tests.yml). The GitLab runner only runs protected branches (`main`). The Docker images are not
built on GitLab, because its container registry is not enabled for the project; they come from Docker Hub.

## Biosecurity screening (COMMEC): details

Before the builder computes the final design in step 4, every sequence
entered by the user (cargo, own shell, own module parts) is checked
by COMMEC for hits against a curated list of known toxins,
virulence factors and regulated pathogens. A hit blocks the
design: a warning with a rationale is shown, and no construct, no parts and no
order list are generated until the flagged sequence is changed or removed. There is no
confirm-and-continue button.

**Runs as a second container by default**, because COMMEC needs Conda and
BLAST/HMMER. That does not fit into the slim main image and is not
installed automatically (unlike primer3-py), hence the
separate sidecar container instead of a built-in check. Deliberately no longer
plain opt-in: a safety check that had to be switched on manually
would too easily be forgotten or skipped in everyday use. If `commec` is
once not reachable (e.g. while starting up, or with `COMMEC_URL`
set to empty manually), the builder does not calculate a construct: the
header badge says "Biosecurity screening: off" and "Calculate construct"
shows a message instead. The switch `REQUIRE_SCREENING` in
`frontend/index.html` (default `true`) can be set to `false` for testing
only; the result then says that the sequences were not screened. Real
unavoidability cannot be guaranteed by self-hosted, open source software anyway,
so this is the honest default here, not a tamper protection.

**Database scope:** The shipped `commec-service` container (commec 1.0.4, the newest version
that installs on Windows, Linux and Mac incl. Apple Silicon) downloads the curated commec databases
(biorisk and low-concern; ~1.2 GB) on its first start into the volume `commec-db`, so a
recreated container does not download them again. It does not download the full
protein/nucleotide taxonomy databases (over 1 TB together according to
COMMEC's own size statement), which on most machines neither fit on the
disk nor download in a reasonable time. That means: no
taxonomy best match against arbitrary organisms, only direct hits against the
curated biorisk list. Details and consequences (among others how generic
"Warning" results for unchecked but harmless sequences are handled)
are in [commec-service/README.md](../commec-service/README.md).

With Docker Compose `app` and `commec` find each other automatically through the
Compose-internal host name (`COMMEC_URL` in `docker-compose.yml` points
to `http://commec:8787` by default). For local development without Docker:

```bash
COMMEC_URL=http://localhost:8787 pnpm dev
```

(after the `commec` container has been started separately, e.g. with
`docker compose up commec`).

**Verified:** The complete flow (container build, real
`commec screen` call, frontend gate including the blocking warning) was tested end to end
against a really built and running container, including
a positive test with a real conotoxin sequence obtained from UniProt,
which was correctly detected as "Flag" and triggered the blocking warning.

## Extending the Open NC Database

The Open NC Database (`/selector/`) reads its data from individual
JSON files under [encapsulin_selector/data/](../encapsulin_selector/data/):
adding a new nanocompartment means: copy the template, fill in the fields,
start `pnpm dev`. See
[encapsulin_selector/data/README.md](../encapsulin_selector/data/README.md).
