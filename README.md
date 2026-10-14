# ENCORE-Builder

Golden Gate design software for planning an encapsulin cargo construct with our
Golden Gate toolbox: put together a nanocompartment and a cargo, and get
primers and a finished Level 2 plasmid map, plus a separate filter tool
to find the matching encapsulin.

## Quick start: just use the software

You only need [Docker](https://www.docker.com/products/docker-desktop/)
installed. No programming skills, no Node.js, no Python needed.

1. Download the repo:
   ```bash
   git clone https://github.com/iGEM-KIT/ENCORE-Builder.git
   cd ENCORE-Builder
   ```
2. Start it:
   ```bash
   docker compose up --build
   ```
   The first start takes a bit longer (it builds the builder and additionally
   the biosecurity screening container (commec) downloads its databases (~6 GB download, ~40 GB on disk) once on its first start, see below; the screening is "off" until
   that is done).
3. Open it in the browser: **[http://localhost:3000](http://localhost:3000)**
4. To stop, press `Ctrl+C` in the terminal, or in a new terminal:
   ```bash
   docker compose down
   ```

That's it: the builder and the encapsulin filter are now fully running.

### Biosecurity screening is always included

Every gene sequence you enter yourself is automatically checked for known toxins,
virulence factors and regulated pathogens
([COMMEC](https://github.com/ibbis-bio/common-mechanism) by IBBIS). For this,
`docker compose up` starts a second container by default, without
having to specify anything extra. As soon as both containers are running,
the header at the top right shows **"Biosecurity screening: on"** with a
green dot.

## Using the software

The start page has a **"Before you start"** card that opens a guide with all rules and
notes for using the builder (what the builder accepts, which combinations are
allowed, what happens to your sequences). Read it once.

1. Start page → **"Start builder"**
2. **Step 1, Nanocompartment Site:** choose a nanocompartment from the library
   (or paste your own sequence) and fill the four modules around it
   (spacer, linker, surface marker or own sequence)
3. **Step 2, Cargo Site:** paste your own CDS or amino acid sequence (or load an
   example such as GFP) and fill the modules around it
4. **Step 3, Promoter:** choose the promoter
5. Click **"Calculate construct"**. With screening active it runs automatically;
   only for a real hit a warning appears that has to be confirmed before
   continuing
6. **Step 4, Modules:** the finished Golden Gate design (Level 0 → 1 → 2), primers,
   plasmid map, exportable as an annotated GenBank file (.gb)
7. **Step 5, Order:** what to order as oligos, primers or DNA

Every sequence you enter yourself (DNA or amino acids) is codon-optimized for
*S. cerevisiae* and kept free of BsaI and BbsI sites.

Not sure yet which encapsulin fits? Switch to **"Encapsulin Filter"** in the
header at the top: there you can search by organism/accession or filter by
physical properties (diameter, triangulation number).

---

## For developers

### Local development (without Docker)

Requirements: Node.js ≥20.19 and [pnpm](https://pnpm.io/).

```bash
pnpm install
pnpm dev
```

On the first start `pnpm dev` automatically creates a `.venv` with primer3-py
([scripts/setup-python.mjs](scripts/setup-python.mjs)), so no manual
`pip install` is needed. If there is no Python 3 on the PATH or the installation
fails (e.g. missing C compiler), Biologik keeps running anyway, only with
a less accurate Wallace Tm estimate instead of primer3. A specific
interpreter can be forced with `BIOLOGIK_PYTHON=/path/to/python`.

Alternatively Docker without Compose:

```bash
docker build -t encore-builder .
docker run -p 3000:3000 encore-builder
```

### Biosecurity screening (COMMEC): details

Before the builder computes the final design in step 4, every sequence
entered by the user (cargo, own shell, own module parts) is checked
by COMMEC for hits against a curated list of known toxins,
virulence factors and regulated pathogens. A hit does not block the
design automatically, but shows a warning with a rationale that the
user has to confirm explicitly before they can continue.

**Runs as a second container by default**, because COMMEC needs Conda and
BLAST/HMMER. That does not fit into the slim main image and is not
installed automatically (unlike primer3-py), hence the
separate sidecar container instead of a built-in check. Deliberately no longer
plain opt-in: a safety check that had to be switched on manually
would too easily be forgotten or skipped in everyday use. If `commec` is
once not reachable (e.g. while starting up, or with `COMMEC_URL`
set to empty manually), the builder keeps running normally, only without
this screening (with a visible note in step 4). Real
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
are in [commec-service/README.md](commec-service/README.md).

With Docker Compose `app` and `commec` find each other automatically through the
Compose-internal host name (`COMMEC_URL` in `docker-compose.yml` points
to `http://commec:8787` by default). For local development without Docker:

```bash
COMMEC_URL=http://localhost:8787 pnpm dev
```

(after the `commec` container has been started separately, e.g. with
`docker compose up commec`).

**Verified:** The complete flow (container build, real
`commec screen` call, frontend gate including warning modal) was tested end to end
against a really built and running container, including
a positive test with a real conotoxin sequence obtained from UniProt,
which was correctly detected as "Flag" and triggered the warning modal.

### Extending the encapsulin database

The encapsulin filter (`/selector/`) reads its data from individual
JSON files under [encapsulin_selector/data/](encapsulin_selector/data/):
adding a new encapsulin means: copy the template, fill in the fields,
start `pnpm dev`. See
[encapsulin_selector/data/README.md](encapsulin_selector/data/README.md).

# Permission
Some might encounter troubles while pushing it to the max. How weird.
