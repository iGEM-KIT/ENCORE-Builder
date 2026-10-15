# ENCORE Builder

The ENCORE Builder is a design tool for planning an encapsulin cargo construct with our
Golden Gate toolKIT. You put together a nanocompartment and a cargo, and the Builder gives you
all parts, primers or oligos to order and a finished Level 2 plasmid map. A second tool, the
Encapsulin Filter, helps you to find the matching encapsulin first.

It runs on your own computer, inside a program called Docker. Nothing you type leaves your
computer. This page explains every way to start it, step by step. You do not need programming
skills.

**Contents**

1. [Which way is right for me?](#which-way-is-right-for-me)
2. [Step 0: install Docker (all ways)](#step-0-install-docker-all-ways)
3. [Way A: easiest, download one file](#way-a-easiest-download-one-file)
4. [Way B: download the whole project and build it yourself](#way-b-download-the-whole-project-and-build-it-yourself)
5. [Docker Desktop window](#using-the-docker-desktop-window)
6. [Biosecurity screening is always included](#biosecurity-screening-is-always-included)
7. [Using the software](#using-the-software)
8. [Stopping, updating and cleaning up](#stopping-updating-and-cleaning-up)
9. [Something does not work](#something-does-not-work)
10. [For developers](#for-developers)

## Which way is right for me?

Both ways always start **two containers together**: the Builder (with the Encapsulin Filter) and
the biosecurity screening. There is no way to run the Builder without the screening.

| | Way A | Way B |
|---|---|---|
| For whom | Everybody. Start here. | People who want to read or change the code |
| You download | one small file | the whole project |
| Where the program comes from | ready-made images from the GitHub Container Registry | built on your computer |
| First start | a few minutes | 10 to 30 minutes |

Both ways need Docker (Step 0). If you are unsure, take **Way A**.

## Step 0: install Docker (all ways)

Docker is a free program that runs other programs in a protected box (a "container"), so that
you do not have to install anything else. You only need to do this once.

1. Go to [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/)
   and download **Docker Desktop** for your system (Windows, Mac with Apple chip or Intel chip,
   or Linux). Not sure about your Mac? Click the Apple menu, then "About This Mac": if it says
   "Apple M1/M2/M3/M4" you have the Apple chip.
2. Open the downloaded file and follow the installer. Accept the standard settings. On Windows
   the installer may ask for a restart.
3. **Start Docker Desktop** and wait until it says "Engine running" (a green dot at the bottom
   left). You can skip creating an account; there is a "Skip" or "Continue without signing in"
   option.
4. Docker Desktop has to be running whenever you use the ENCORE Builder.

Good to know before you start:

* Free disk space: about **5 GB** (the program itself and the screening databases).
* Memory: Docker Desktop should be allowed to use at least **4 GB** (Settings, Resources).
* Internet: needed for the first start only (downloads), afterwards the Builder works offline.

### How to open a terminal (needed for the commands below)

A terminal is a window where you type a command and press Enter.

* **Windows:** press the Windows key, type `PowerShell`, press Enter.
* **Mac:** press Cmd and Space, type `Terminal`, press Enter.
* **Linux:** press Ctrl, Alt and T.

To run a command, copy it from this page, paste it into the terminal and press **Enter**.
Where a step says "go into the folder", type `cd ` (with a space after it), drag the folder
from your file explorer into the terminal window (this fills in its path) and press Enter.

## Way A: easiest, download one file

You download a single small file. Docker then fetches the ready-made program and the biosecurity
screening for you.

1. Create a new empty folder, for example `ENCORE` on your Desktop.
2. Download this file into that folder:
   [docker-compose.pull.yml](https://raw.githubusercontent.com/iGEM-KIT/ENCORE-Builder/main/docker-compose.pull.yml)
   (right-click the link, "Save link as"; make sure the file name stays exactly
   `docker-compose.pull.yml`).
3. Open a terminal and go into the folder (see above).
4. Type this and press Enter:
   ```bash
   docker compose -f docker-compose.pull.yml up
   ```
5. Wait. The **first start takes several minutes**: Docker downloads the program, and the
   screening container downloads its databases (about 1.2 GB) once. Lines of text keep scrolling
   by; that is normal. Later starts take seconds.
6. Open your web browser and go to **[http://localhost:3000](http://localhost:3000)**.
   If you see "Upgrade Required" instead of the page, use
   [http://127.0.0.1:3000](http://127.0.0.1:3000).
7. In the top right the page shows **"Biosecurity screening: on"** with a green dot as soon as
   the screening is ready. Until then it says "off"; the Builder already works, just without
   the check. If you want the screening, wait for the dot before you calculate a construct.

To stop the program, see [Stopping, updating and cleaning up](#stopping-updating-and-cleaning-up).

## Way B: download the whole project and build it yourself

Choose this if you want to read or change the code, or if you prefer to build the program
yourself instead of trusting a ready-made image. Docker builds everything from the project files.

1. Download the project. Without any extra software: open
   [github.com/iGEM-KIT/ENCORE-Builder](https://github.com/iGEM-KIT/ENCORE-Builder), click the
   green **Code** button, then **Download ZIP**, and unzip the file. If you know git, you can
   instead run:
   ```bash
   git clone https://github.com/iGEM-KIT/ENCORE-Builder.git
   ```
2. Open a terminal and go into the unzipped folder `ENCORE-Builder` (see above).
3. Build and start:
   ```bash
   docker compose up --build
   ```
4. The first start takes longer than Way A (10 to 30 minutes, depending on your computer and
   internet), because Docker builds both images and the screening downloads its databases once.
5. Open **[http://localhost:3000](http://localhost:3000)** (or
   [http://127.0.0.1:3000](http://127.0.0.1:3000) if you see "Upgrade Required").

The same folder also works without building: `docker compose up` (without `--build`) uses the
ready-made images like Way A.

## Using the Docker Desktop window

Docker Desktop shows the program as a project in the **Containers** tab after the first start
of Way A or B. There you can start and stop both containers together with one button, read the
logs and open the page with the port link next to `app`. Typing a command is only needed for
the very first start.

## Biosecurity screening is always included

Every gene sequence you enter yourself is automatically checked for known toxins, virulence
factors and regulated pathogens
([COMMEC](https://github.com/ibbis-bio/common-mechanism) by IBBIS). If a sequence matches, a
warning with a reason appears and you have to confirm it before you can continue. It is a
helper check and does not replace the biosafety review of your institution.

## Using the software

The start page has a **"Before you start"** card that opens a guide with all rules and
notes for using the builder (what the builder accepts, which combinations are
allowed, what happens to your sequences). Read it once.

1. Start page, then **"Start builder"**
2. **Step 1, Nanocompartment Site:** choose a nanocompartment from the library
   (or paste your own sequence) and fill the four modules around it
   (spacer, linker, surface marker or own sequence)
3. **Step 2, Cargo Site:** paste your own coding sequence or amino acid sequence (or load an
   example such as GFP) and fill the modules around it
4. **Step 3, Promoter:** choose the promoter
5. Click **"Calculate construct"**. With screening active it runs automatically;
   only for a real hit a warning appears that has to be confirmed before
   continuing
6. **Step 4, Modules:** the finished Golden Gate design (Level 0, 1 and 2), primers,
   plasmid map, exportable as an annotated GenBank file (.gb)
7. **Step 5, Overview:** what to order as oligos, primers or DNA

Every sequence you enter yourself (DNA or amino acids) is codon-optimized for
*S. cerevisiae* and kept free of BsaI and BbsI sites.

Not sure yet which encapsulin fits? Switch to **"Encapsulin Filter"** in the
header at the top: there you can search by organism or accession, or filter by
physical properties (diameter, triangulation number).

## Stopping, updating and cleaning up

Open the terminal in the same folder you started from (Way A: the folder with
`docker-compose.pull.yml`, Way B: the project folder).

| I want to | Way A | Way B |
|---|---|---|
| Stop | press `Ctrl+C` in the terminal where it runs, or run `docker compose -f docker-compose.pull.yml down` | `docker compose down` |
| Start again | `docker compose -f docker-compose.pull.yml up` | `docker compose up` |
| Run in the background | add `-d` to the start command; stop it with the `down` command | same |
| Update to the newest version | `docker compose -f docker-compose.pull.yml pull`, then start again | `git pull` (or download the ZIP again), then `docker compose up --build` |

You can also stop and start the containers with the buttons in the **Containers** tab of Docker
Desktop.

Remove everything again, including the downloaded screening databases (frees about 5 GB):

```bash
docker compose -f docker-compose.pull.yml down --volumes --rmi all
```

(Way B: `docker compose down --volumes --rmi all`.)

## Something does not work

| Problem | What to do |
|---|---|
| "Cannot connect to the Docker daemon" or "docker: command not found" | Docker Desktop is not running or not installed. Start Docker Desktop and wait for "Engine running". |
| The page shows "Upgrade Required" | Use [http://127.0.0.1:3000](http://127.0.0.1:3000) instead of `localhost`. |
| "port is already allocated" or "address already in use" | Something else uses port 3000. Stop the other program, or change `"3000:3000"` in the compose file to `"3001:3000"` and open port 3001. |
| The header says "Biosecurity screening: off" | The screening container is still downloading its databases (first start only, a few minutes) or not running. Check the **Containers** tab: both `app` and `commec` should be green. |
| The first start seems stuck | Watch the terminal: as long as lines keep appearing, it is downloading. A slow internet connection makes it take longer. |
| "no space left on device" | Free up disk space, or in Docker Desktop use Settings, Resources to give it more disk. |
| It is very slow or crashes on the first start | Give Docker Desktop more memory (Settings, Resources, at least 4 GB). |
| Windows asks about WSL 2 or virtualization | Follow the Docker Desktop installer hints. Virtualization may have to be enabled in the BIOS; the Docker documentation explains how. |

Still stuck? Open an
[issue on GitHub](https://github.com/iGEM-KIT/ENCORE-Builder/issues) and copy the last lines
from the terminal into it.

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

The builder image alone (`docker build -t encore-builder .`) runs without the screening container;
users should always start the Compose files so that the screening is included.

### Publishing the Docker images

The workflow [.github/workflows/publish-images.yml](.github/workflows/publish-images.yml)
builds both images for `linux/amd64` and `linux/arm64` and pushes them to the GitHub Container
Registry on every push to `main`, on version tags (`v1.2.3`) and by hand from the Actions tab:

* `ghcr.io/igem-kit/encore-builder` (builder)
* `ghcr.io/igem-kit/encore-builder-commec` (biosecurity screening)

After the first run, set both packages to **public** on GitHub (organization page, Packages,
package settings, "Change package visibility"), otherwise users cannot pull them without
logging in. `docker-compose.yml` has both `image:` and `build:` for every service, so
`docker compose up --build` builds locally and plain `docker compose up` pulls;
`docker-compose.pull.yml` is the image-only variant that users download as a single file.

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
