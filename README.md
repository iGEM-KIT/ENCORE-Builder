# ENCORE-Builder

The ENCORE-Builder is a design tool for planning an encapsulin cargo construct with our
Golden Gate toolKIT. You put together a nanocompartment and a cargo, and the Builder gives you
all parts, primers or oligos to order and a finished Level 2 plasmid map. A second tool, the
Open NC Database, helps you to find the matching shell first.

It runs on your own computer, inside a program called Docker. Nothing you type leaves your
computer. This page explains how to start it, step by step. You do not need programming
skills.

**Who is it for?** For iGEM teams and labs that want to build an encapsulin cargo construct
with Golden Gate cloning in yeast and do not want to plan every part, overhang and primer by
hand. The Builder is meant for wet lab members without programming experience. The Open NC
Database is meant for everyone who wants to compare encapsulin shells before choosing one.

**Contents**

1. [Where the project lives](#where-the-project-lives)
2. [Step 1: install Docker](#step-1-install-docker)
3. [Step 2: download and start](#step-2-download-and-start)
4. [Using the Docker Desktop window](#using-the-docker-desktop-window)
5. [Biosecurity screening is always included](#biosecurity-screening-is-always-included)
6. [Using the software](#using-the-software)
7. [Reproduce the example](#reproduce-the-example)
8. [Stopping, updating and cleaning up](#stopping-updating-and-cleaning-up)
9. [Something does not work](#something-does-not-work)
10. [For developers](#for-developers)

## Where the project lives

The project is published on two websites with the same files and this same README. Either one
works for the download, because the program itself (the ready-made Docker images) always comes from
Docker Hub (`igemkit/encore-builder` and `igemkit/encore-builder-commec`).

| | Website | Address |
|---|---|---|
| GitHub | the team repository | [github.com/iGEM-KIT/ENCORE-Builder](https://github.com/iGEM-KIT/ENCORE-Builder) |
| GitLab | the repository of the iGEM competition | [gitlab.igem.org/2026/software/kit/encore-software](https://gitlab.igem.org/2026/software/kit/encore-software) |

The Builder always starts **two containers together**: the Builder (with the Open NC Database) and
the biosecurity screening. There is no way to run the Builder without the screening.

## Step 1: install Docker

Docker is a free program that runs other programs in a protected box (a "container"), so that
you do not have to install anything else. You only need to do this once.

**Windows only: install WSL 2 first.** Docker Desktop on Windows runs on the Windows Subsystem for Linux (WSL 2), so
install that before Docker Desktop. Skip this block on Mac and Linux.

1. Open the Start menu, type `PowerShell`, right-click **Windows PowerShell** and choose **Run as administrator**.
2. Type this and press Enter:
   ```bash
   wsl --install
   ```
3. Wait until it is finished, then **restart the computer**.
4. After the restart a window opens and finishes the download of Linux (Ubuntu). Wait for it, then **create a user
   account**: type a user name and press Enter, then choose a password (nothing is shown while you type it) and
   repeat it. This account exists only on your computer for Linux, it is not an online account. Remember the password,
   but you will rarely need it. When the window shows a prompt like `name@computer:~$`, the setup is done and you can
   close it.
5. If the command fails or says that virtualization is off, switch on virtualization in the BIOS (it is called
   "Intel VT-x", "AMD-V" or "SVM Mode", depending on the computer) and run the command again. WSL 2 needs Windows 10
   (version 2004 or newer) or Windows 11.

Now continue with Docker Desktop:

1. Go to [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/)
   and download **Docker Desktop** for your system (Windows, Mac with Apple chip or Intel chip,
   or Linux). Not sure about your Mac? Click the Apple menu, then "About This Mac": if it says
   "Apple M1/M2/M3/M4" you have the Apple chip.
2. Open the downloaded file and follow the installer. Accept the standard settings. On Windows
   the installer may ask for a restart.
3. **Start Docker Desktop** and wait until it says "Engine running" (a green dot at the bottom
   left). You can skip creating an account; there is a "Skip" or "Continue without signing in"
   option.
4. Docker Desktop has to be running whenever you use the ENCORE-Builder.

Good to know before you start:

* Free disk space: about **5 GB** (the program itself and the screening databases).
* Memory: Docker Desktop should be allowed to use at least **4 GB** (Settings, Resources).
* Internet: needed for the first start and for updates, afterwards the Builder works offline.

## Step 2: download and start

1. **Download the project.** Open [GitHub](https://github.com/iGEM-KIT/ENCORE-Builder) and click the
   green **Code** button, then **Download ZIP**. On GitLab click the blue **Code** button, then
   **zip** under **Download source code**.
2. **Unzip it** (Windows: right-click the file, **Extract All**; Mac: double-click it). Put the
   unzipped folder somewhere normal, for example on your Desktop. On Windows use a normal Windows
   folder, not a folder inside Linux (WSL/Ubuntu).
3. Start **Docker Desktop** and wait for "Engine running".
4. **Double-click the start file** in the unzipped folder:
   * Windows: `start.bat`. If a blue box says Windows protected your PC, click **More info**, then **Run anyway**.
   * Mac: `start.command`. The first time, the Mac may say that it cannot check the file. Right-click
     the file and choose **Open**, then **Open** again. On a newer Mac that does not offer this, open
     Apple menu, System Settings, Privacy & Security and click **Open Anyway** next to the message about `start.command`.
   * Linux: open a terminal in the folder and run `bash start.command`.
5. Wait. The **first start takes several minutes**: Docker downloads the program, and the
   screening container downloads its databases (about 1.2 GB) once. Lines of text keep scrolling
   by; that is normal. Later starts take seconds.
6. Your web browser opens by itself at **[http://localhost:3000](http://localhost:3000)**. If it does
   not, open that address yourself.
7. In the top right the page shows **"Biosecurity screening: on"** with a green dot as soon as
   the screening is ready. Until then it says "off" and the Builder does not calculate a
   construct (it shows a message instead). Wait for the green dot before you calculate.

You can close the start window when it says "Ready". The program keeps running in Docker Desktop.
The start file does the same job every time: it fetches the newest version from Docker Hub,
starts both containers and opens the page. So **starting again is also the update**.

To stop the program, see [Stopping, updating and cleaning up](#stopping-updating-and-cleaning-up).

**If you prefer the terminal.** Open a terminal inside the unzipped folder (Windows: click into the address
bar of the folder in File Explorer, type `powershell.exe` and press Enter; Mac: drag the folder onto the Terminal icon
in the Dock) and run:

```bash
docker compose -f docker-compose.pull.yml up -d
```

## Using the Docker Desktop window

Docker Desktop shows the program as a project in the **Containers** tab after the first start.
There you can start and stop both containers together with one button, read the logs and open
the page with the port link next to `app`.

## Biosecurity screening is always included

Every gene sequence you enter yourself is automatically checked for known toxins, virulence
factors and regulated pathogens
([COMMEC](https://github.com/ibbis-bio/common-mechanism) by IBBIS). If a sequence matches, a
warning with a reason appears and the Builder does not build a construct, parts or an order list
until you change or remove the flagged sequence. It is a helper check and does not replace the biosafety review of your institution.

## Using the software

Everything you need to know to use the software is explained in the **guide inside the
software itself**. On the start page, click the **"Before you start"** card: it opens a guide
with all rules and notes (what the builder accepts, which combinations are allowed, how your
own sequences are handled, how to read the results and what to order). Read it once before you
start.

## Reproduce the example

You can check that your installation calculates correctly with one fixed example: the design of
the construct that we also cloned in the lab (see the page Oxygen-Free Space of our wiki). It
uses the shell of *Quasibacillus thermotolerans* (E-Qt) and the cargo LGB4. The cargo carries a
SpyTag, a 3×(GSSS) linker and two NCS spacers. The shell carries a SpyCatcher, a 3×(GSSS) linker
and two NCS spacers. The promoter is GAL1-10.

**In the Builder:** choose the shell *Quasibacillus thermotolerans*, the cargo *LGB4* and the
promoter *GAL1-10*. In the cargo module put the marker SpyTag in Type 0.1 and the linker 3×(GSSS)
in Type 0.2. In the nanocompartment module put the marker SpyCatcher in Type 0.1 and the linker
3×(GSSS) in Type 0.2. Leave Type 0.4 and 0.5 as NCS in both modules.

**Without the web page** (needs Python 3 and the packages of `Biologik/requirements.txt`),
from the project folder:

```bash
python3 -m Biologik.level0_design.cli design < docs/examples/oxygen-free-space-request.json
```

The request is the file [docs/examples/oxygen-free-space-request.json](docs/examples/oxygen-free-space-request.json).

**What you should get:**

| Result | Value |
|---|---|
| Cargo module (antisense) | SpyTag, 3×(GSSS), LGB4, NCS, NCS (Type 0.1 to 0.5) |
| Promoter | GAL1-10 |
| Nanocompartment module (sense) | SpyCatcher, 3×(GSSS), E-Qt, NCS, NCS (Type 0.1 to 0.5) |
| Level 1 constructs | Level1_Cargo, Level1_Promoter, Level1_NC |
| Junction overhangs of Level 2 | CCAA, CGTT, TGAT, AATG |
| Level 2 insert | 2555 bp |
| Level 2 plasmid (pESC-HIS) | 8274 bp |
| Cargo primers | `GGTCTCNCCAAGAAGGCTTTCTTTATGGCCGCCG` and `GGTCTCNGCAAGGTGCTTTCACGGAAAAGCAAGAGG` |

The result is the same on every run, because no part of this example is codon optimized with a
random draw. If you give your own sequences, the codon optimization uses a weighted random draw,
so the exact bases of those parts can differ between runs while the rules (no forbidden sites,
same protein) stay the same. The test
[tests/unit/biologik/test_reference_example.py](tests/unit/biologik/test_reference_example.py)
runs this example on every push, so the numbers above stay correct.

## Stopping, updating and cleaning up

Everything is easiest in the **Docker Desktop window**: open Docker Desktop and use the
**Containers** tab. Both containers appear there together as one entry named after your folder
(for example `encore-builder`), with the two containers `app` and `commec` inside.

| I want to | Docker Desktop window | Terminal (in the folder with the start file) |
|---|---|---|
| Stop | **Containers** tab, click the **Stop** button (square) on the entry of the project | `docker compose -f docker-compose.pull.yml down` |
| Start again | double-click the start file, or in the **Containers** tab click the **Start** button (triangle) on the entry and wait for `app` and `commec` to turn green | `docker compose -f docker-compose.pull.yml up -d` |
| Open the page | **Containers** tab, click the port link `3000:3000` next to `app` | open [http://localhost:3000](http://localhost:3000) |
| Look at the logs | click `app` or `commec`, then the **Logs** tab | `docker compose -f docker-compose.pull.yml logs` |
| Update to the newest version | double-click the start file again, it fetches the newest version from Docker Hub first | `docker compose -f docker-compose.pull.yml pull`, then start again |
| Remove the program but keep the screening databases | **Containers** tab, **Delete** (trash can) on the entry of the project | `docker compose -f docker-compose.pull.yml down` |
| Remove everything, including the downloaded screening databases (frees about 5 GB) | delete the project in the **Containers** tab, then delete the two `igemkit/...` images in the **Images** tab and the volume ending in `commec-db` in the **Volumes** tab | `docker compose -f docker-compose.pull.yml down --volumes --rmi all` |

### After an update: old images

After an update, Docker Desktop shows the previous version of each image in the **Images** tab
with the name `<none>` (the name moved to the new image). These old images are no longer used and
**can safely be deleted** (select them in the **Images** tab and click the trash can) to free
disk space. The new images with the proper name stay.

## Something does not work

| Problem | What to do |
|---|---|
| The start file says "Docker is not running" | Start Docker Desktop, wait for "Engine running" and double-click the start file again. |
| "Cannot connect to the Docker daemon" or "docker: command not found" | Docker Desktop is not running or not installed. Start Docker Desktop and wait for "Engine running". |
| "failed to connect to the docker API at unix:///var/run/docker.sock" | Docker Desktop is not running yet, or the terminal uses the wrong Docker connection. Start Docker Desktop and wait for "Engine running". If the message stays, run `docker context use desktop-linux` once and try again. |
| "port is already allocated" or "address already in use" | Something else uses port 3000. Stop the other program, or change `"3000:3000"` in the file `docker-compose.pull.yml` to `"3001:3000"` and open port 3001. |
| The page shows "The Builder cannot be reached" (or "Failed to fetch") | The browser cannot reach the Builder. In Docker Desktop open the **Containers** tab and check that `app` is running (green); start it if not, wait a few seconds and reload the page. This also happens when the containers were restarted or updated while the page was still open. The screening container (`commec`) is not the cause: without it the Builder still calculates, only without the check. |
| The header says "Biosecurity screening: off" | The screening container is still downloading its databases (first start only, a few minutes) or not running. As long as it says "off", the Builder does not calculate any construct. Check the **Containers** tab: both `app` and `commec` should be green. |
| The first start seems stuck | Watch the window of the start file: as long as lines keep appearing, it is downloading. A slow internet connection makes it take longer. |
| "no space left on device" | Free up disk space, or in Docker Desktop use Settings, Resources to give it more disk. |
| It is very slow or crashes on the first start | Give Docker Desktop more memory (Settings, Resources, at least 4 GB). |
| Windows asks about WSL 2 or virtualization, or Docker Desktop says "WSL needs updating" | Install WSL 2 as described in Step 1 (`wsl --install` in an administrator PowerShell, then restart). If Docker Desktop still complains, run `wsl --update` once and restart Docker Desktop. Virtualization may have to be enabled in the BIOS; the Docker documentation explains how. |

Still stuck? Open an
[issue on GitHub](https://github.com/iGEM-KIT/ENCORE-Builder/issues) (or on GitLab, if you work there) and copy the last lines
from the start window into it or send a mail to [Fese1000](https://github.com/Fese1000).

---

## For developers

### How it is built

A picture of the parts and the data flow is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
The HTTP interface is described in [docs/openapi.yaml](docs/openapi.yaml) (OpenAPI 3), so that
other tools can call the Builder.

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

The main image alone (`docker build -t encore-builder .`, ENCORE-Builder and Open NC Database) starts without the screening container,
but then it does not calculate any construct. Users should always start the Compose files so that the
screening is included.

### Calling the Builder from a script

The Builder has a small HTTP interface, described in [docs/openapi.yaml](docs/openapi.yaml). With the
software running on port 3000 (started with the start file or `pnpm dev`), a design of the example above looks like this:

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
browser from the same GenBank text by [frontend/sbol.js](frontend/sbol.js), so the API and the command line return GenBank only.
The same calculation runs without the web server:
`python3 -m Biologik.level0_design.cli design < request.json`.

### Adding a part

The part files are plain JSON in
[Biologik/level0_design/parts/](Biologik/level0_design/parts/README.md). No build and no restart is needed, the
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
[encapsulin_selector/data/README.md](encapsulin_selector/data/README.md).

### Publishing the Docker images

The workflow [.github/workflows/publish-images.yml](.github/workflows/publish-images.yml)
builds both images for `linux/amd64` and `linux/arm64` and pushes them to Docker Hub and to the GitHub Container
Registry on every push to `main`, on version tags (`v1.2.3`) and by hand from the Actions tab:

* `igemkit/encore-builder` (ENCORE-Builder and Open NC Database)
* `igemkit/encore-builder-commec` (biosecurity screening)

Both are also published as `ghcr.io/igem-kit/...`. The workflow needs the repository secrets
`DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` (a Docker Hub access token with Read & Write permission).

`docker-compose.yml` has both `image:` and `build:` for every service, so
`docker compose up --build` builds both images from the source code (10 to 30 minutes) and plain
`docker compose up` pulls them from Docker Hub; `docker-compose.pull.yml` is the image-only variant that
the start files `start.command` and `start.bat` use.

### Running the tests

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

The workflow [.github/workflows/tests.yml](.github/workflows/tests.yml) runs everything on every push to `main` and on every
pull request. The interactive parts of the pages (clicking through the steps) are not covered by an automated test yet.

### Biosecurity screening (COMMEC): details

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
`commec screen` call, frontend gate including the blocking warning) was tested end to end
against a really built and running container, including
a positive test with a real conotoxin sequence obtained from UniProt,
which was correctly detected as "Flag" and triggered the blocking warning.

### Extending the Open NC Database

The Open NC Database (`/selector/`) reads its data from individual
JSON files under [encapsulin_selector/data/](encapsulin_selector/data/):
adding a new nanocompartment means: copy the template, fill in the fields,
start `pnpm dev`. See
[encapsulin_selector/data/README.md](encapsulin_selector/data/README.md).

## Use of AI

An AI coding assistant, Claude Code by Anthropic (model Claude Sonnet 5.5), helped to build this software. It was used to write and change
program code, tests, documentation, the in-app guide and the texts of the interface, and to translate the interface into the seven other languages.
Commits that were made with this help carry a `Co-Authored-By: Claude` line in the git history.

* The design decisions, the scientific content (the curated data of the Open NC Database, the toolKIT parts and their sequences) and the
  checks against the lab come from the team. The assistant did not produce experimental results.
* The translations were written with the assistant and have not been proofread by native speakers. They can contain mistakes.
* The team remains responsible for everything in this repository. Please open an issue if you find an error.

## License

The code of this repository is released under the [MIT License](LICENSE), copyright 2026 iGEM-KIT (see [NOTICE](NOTICE)).
Third-party components (for example primer3-py, COMMEC, the Nuxt packages) keep
their own licenses. The data of the Open NC Database come from UniProt, the
PDB and the cited publications and stay under the terms of those sources.
