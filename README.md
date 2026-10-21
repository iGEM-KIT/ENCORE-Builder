# ENCORE-Builder

The ENCORE-Builder is a design tool for planning an encapsulin cargo construct with our
Golden Gate toolKIT. You put together a nanocompartment and a cargo, and the Builder gives you
all parts, primers or oligos to order and a finished Level 2 plasmid map. A second tool, the
Open NC Database, helps you to find the matching shell first.

It runs on your own computer, inside a program called Docker. This page explains how to start it,
step by step. You do not need programming skills.

**Who is it for?** For iGEM teams and labs that want to build an encapsulin cargo construct
with Golden Gate cloning in yeast and do not want to plan every part, overhang and primer by
hand. The Builder is meant for wet lab members without programming experience. The Open NC
Database is meant for everyone who wants to compare encapsulin shells before choosing one.

**Contents**

1. [Where the project lives](#where-the-project-lives)
2. [Step 1: install Docker](#step-1-install-docker)
3. [Step 2: get the program from Docker Hub](#step-2-get-the-program-from-docker-hub)
4. [Step 3: start the two containers](#step-3-start-the-two-containers)
5. [Using the Docker Desktop window](#using-the-docker-desktop-window)
6. [Biosecurity screening is always included](#biosecurity-screening-is-always-included)
7. [Using the software](#using-the-software)
8. [Reproduce the example](#reproduce-the-example)
9. [Stopping, updating and cleaning up](#stopping-updating-and-cleaning-up)
10. [Something does not work](#something-does-not-work)

## Where the project lives

The project is published on two websites with the same files and this same README. To use the
program you do not need either of them: the ready-made program is on
[Docker Hub](https://hub.docker.com/u/igemkit) (`igemkit/encore-builder` and
`igemkit/encore-builder-commec`). The websites hold the source code.

| | Website | Address |
|---|---|---|
| GitHub | the team repository | [github.com/iGEM-KIT/ENCORE-Builder](https://github.com/iGEM-KIT/ENCORE-Builder) |
| GitLab | the repository of the iGEM competition | [gitlab.igem.org/2026/software/kit/encore-software](https://gitlab.igem.org/2026/software/kit/encore-software) |

The program always consists of **two containers**: the Builder (with the Open NC Database) and
the biosecurity screening. There is no way to use the Builder without the screening.

## Step 1: install Docker

Docker is a free program that runs other programs in a protected box (a "container"), so that
you do not have to install anything else. You only need to do this once.

**Windows only: install WSL 2 first.** Docker Desktop on Windows needs the Windows Subsystem for Linux
(WSL 2). The Docker installer often sets it up by itself, but installing it first avoids errors.
Skip this block on Mac and Linux.

1. Open the Start menu, type `PowerShell`, right-click **Windows PowerShell** and choose **Run as administrator**.
2. Type this and press Enter:
   ```bash
   wsl --install
   ```
3. Wait until it is finished. Restart the computer only if Windows asks for it.
4. A window opens and finishes the download of Linux (Ubuntu). Wait for it, then **create a user
   account**: type a user name and press Enter, then choose a password (nothing is shown while you type it) and
   repeat it. This account exists only on your computer for Linux, it is not an online account. Remember the password,
   but you will rarely need it. When the window shows a prompt like `name@computer:~$`, the setup is done and you can
   close it.
5. If the command fails or says that virtualization is off, switch on virtualization in the BIOS (it is called
   "Intel VT-x", "AMD-V" or "SVM Mode", depending on the computer) and run the command again. Docker Desktop needs Windows 10
   (version 21H2 or newer) or Windows 11.

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

## Step 2: get the program from Docker Hub

The ready-made program is on Docker Hub, the app store of Docker. You pull it with a few clicks in
Docker Desktop. There is nothing to download from GitHub or GitLab. There are two images, because
the Builder always runs together with the biosecurity screening:

* `igemkit/encore-builder`: the ENCORE-Builder and the Open NC Database
* `igemkit/encore-builder-commec`: the biosecurity screening

1. Start **Docker Desktop** and wait for "Engine running".
2. Click the search field at the top (or press Ctrl+K, on a Mac Cmd+K) and type `igemkit`.
3. In the results find `igemkit/encore-builder-commec` and click **Pull**. Do the same for
   `igemkit/encore-builder`. If you cannot find them, check that the **Images** or **Docker Hub** tab
   of the search result is selected.
4. Open the **Images** tab on the left. Both images are now in the list.

## Step 3: start the two containers

Start the screening first, then the Builder. In the **Images** tab, click the **Run** button
(triangle) at the end of the line of an image and open **Optional settings**.

1. **`igemkit/encore-builder-commec`:** enter the host port `8787`. Under **Volumes** enter `commec-db`
   as host path and `/databases` as container path (this keeps the screening databases of about 1.2 GB for
   later updates). Click **Run**.
2. **`igemkit/encore-builder`:** enter the host port `3000` and click **Run**.
3. Wait. The **first start takes several minutes**, because the screening container downloads its
   databases once. Click `commec` in the **Containers** tab and open **Logs** to see what it does.
   Later starts take seconds.
4. Open your web browser and go to **[http://localhost:3000](http://localhost:3000)**.
5. In the top right the page shows **"Biosecurity screening: on"** with a green dot as soon as
   the screening is ready. Until then it says "off" and the Builder does not calculate a
   construct (it shows a message instead). Wait for the green dot before you calculate.

If the volume field insists on a folder, click the folder button and create an empty folder named
`commec-db` on your Desktop.

To stop the program, see [Stopping, updating and cleaning up](#stopping-updating-and-cleaning-up).

**If you prefer the terminal.** One command starts both containers: download the file
[docker-compose.pull.yml](docker-compose.pull.yml), open a terminal in its folder and run:

```bash
docker compose -f docker-compose.pull.yml up -d
```

## Using the Docker Desktop window

Docker Desktop shows the two containers in the **Containers** tab. There you can start and stop each
of them with one button, read the logs and open the page with the port link next to the
Builder (`3000:3000`). Start `commec` before the Builder.

## Biosecurity screening is always included

Every gene sequence you enter yourself is automatically checked for known toxins, virulence
factors and regulated pathogens
([COMMEC](https://github.com/ibbis-bio/common-mechanism) by IBBIS). If a sequence matches, a
warning with a reason appears and the Builder gives you no construct, parts or order list
until you change or remove the flagged sequence. It is an additional check and does not replace the biosafety review of your institution.

## Using the software

Everything you need to know to use the software is explained in the **guide inside the
software itself**. On the start page, click the **"Before you start"** card: it opens a guide
with all rules and notes (what the Builder accepts, which combinations are allowed, how your
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

Everything is done in the **Docker Desktop window**. You start, stop and update both
containers there: the Builder and `commec` (the screening).

| I want to | What to do in Docker Desktop |
|---|---|
| Stop | **Containers** tab, click the **Stop** button (square) on both containers |
| Start again | **Containers** tab, click the **Start** button (triangle) on `commec` first, then on the Builder, and wait until both are green |
| Open the page | **Containers** tab, click the port link `3000:3000` next to the Builder, or open [http://localhost:3000](http://localhost:3000) |
| Look at the logs | click the container, then the **Logs** tab |
| Update to the newest version | see below |
| Remove the program but keep the screening databases | **Containers** tab, **Delete** (trash can) on both containers |
| Remove everything, including the downloaded screening databases (frees about 5 GB) | delete both containers in the **Containers** tab, then delete the two `igemkit/...` images in the **Images** tab and the volume `commec-db` in the **Volumes** tab |

### Update to the newest version

Docker Hub always holds the newest version under the tag `latest`. Your computer keeps the version
it pulled, so you update by pulling again:

1. In the search field at the top type `igemkit` and click **Pull** on `igemkit/encore-builder`
   (and on `igemkit/encore-builder-commec` if the screening changed). Docker only downloads what is new.
2. In the **Containers** tab stop and **delete** the old Builder container (and `commec` if you pulled
   it again). The screening databases are not lost, they live in the volume `commec-db`.
3. Start the containers again with **Run** in the **Images** tab, exactly as in
   [Step 3](#step-3-start-the-two-containers).

After an update, the **Images** tab shows the previous version of each image with the name `<none>`
(the name moved to the new image). These old images are no longer used and **can safely be deleted**
(select them and click the trash can) to free disk space.

## Something does not work

| Problem | What to do |
|---|---|
| "Cannot connect to the Docker daemon" or "docker: command not found" | Docker Desktop is not running or not installed. Start Docker Desktop and wait for "Engine running". |
| "failed to connect to the docker API at unix:///var/run/docker.sock" | Docker Desktop is not running yet, or the terminal uses the wrong Docker connection. Start Docker Desktop and wait for "Engine running". If the message stays, run `docker context use desktop-linux` once and try again. |
| "port is already allocated" or "address already in use" | Something else uses port 3000. Stop the other program, or choose another **Host port** (for example `3001`) when you start the Builder in Step 3 and open that port instead. |
| The page shows "The Builder cannot be reached" (or "Failed to fetch") | The browser cannot reach the Builder. In Docker Desktop open the **Containers** tab and check that the Builder is running (green); start it if not, wait a few seconds and reload the page. This also happens when the containers were restarted or updated while the page was still open. |
| The header says "Biosecurity screening: off" | The screening container is still downloading its databases (first start only, a few minutes) or not running. As long as it says "off", the Builder does not calculate any construct. Check the **Containers** tab: the Builder and `commec` should both be green, and `commec` must have been started with the host port `8787`. |
| The first start seems stuck | Click `commec` in the **Containers** tab and open **Logs**: as long as lines keep appearing, it is downloading. A slow internet connection makes it take longer. |
| "no space left on device" | Free up disk space, or in Docker Desktop use Settings, Resources to give it more disk. |
| It is very slow or crashes on the first start | Give Docker Desktop more memory (Settings, Resources, at least 4 GB). |
| Windows asks about WSL 2 or virtualization, or Docker Desktop says "WSL needs updating" | Install WSL 2 as described in Step 1 (`wsl --install` in an administrator PowerShell, and restart if Windows asks for it). If Docker Desktop still complains, run `wsl --update` once and restart Docker Desktop. Virtualization may have to be enabled in the BIOS; the Docker documentation explains how. |

Still stuck? Open an
[issue on GitHub](https://github.com/iGEM-KIT/ENCORE-Builder/issues) (or on GitLab, if you work there) and copy the last lines
from the Logs tab of the container into it, or contact [Fese1000](https://github.com/Fese1000) on GitHub.

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
