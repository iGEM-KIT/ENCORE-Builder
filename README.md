# ENCORE-Builder
Golden Gate Design Software to plan your cloning process with our Golden Gate Toolbox 

## Docker (empfohlen zum Ausprobieren)

Braucht nur Docker — keine lokale Node- oder Python-Installation:

```bash
docker compose up --build
```

Danach ist die Seite unter [http://localhost:3000](http://localhost:3000) erreichbar. Zum Stoppen `docker compose down`.

Alternativ ohne Compose:

```bash
docker build -t encore-builder .
docker run -p 3000:3000 encore-builder
```

Das Dockerfile installiert primer3-py (für echte Tm/Dimer-Berechnung in Biologik) automatisch beim Build — niemand muss dafür manuell etwas installieren. Schlägt der Install ausnahmsweise fehl, läuft die App trotzdem, nur mit einer ungenaueren Wallace-Tm-Schätzung.

## Lokale Entwicklung (ohne Docker)

```bash
pnpm install
pnpm dev
```

`pnpm dev` legt beim ersten Start automatisch ein `.venv` mit primer3-py an ([scripts/setup-python.mjs](scripts/setup-python.mjs)) — auch hier ist kein manuelles `pip install` nötig. Ist kein Python 3 im PATH oder schlägt die Installation fehl (z. B. fehlender C-Compiler), läuft Biologik trotzdem weiter, nur mit der Wallace-Tm-Schätzung statt primer3. Einen bestimmten Interpreter erzwingen geht über `BIOLOGIK_PYTHON=/pfad/zu/python`.

## Biosecurity screening (COMMEC)

Bevor der Builder in Schritt 4 das finale Design berechnet, wird jede vom
Nutzer selbst eingegebene Sequenz (Cargo, eigene Shell, eigene Modul-Teile)
automatisch per [COMMEC](https://github.com/ibbis-bio/common-mechanism)
("Common Mechanism", IBBIS) auf Treffer gegen eine kuratierte Liste
bekannter Toxine, Virulenzfaktoren und regulierter Pathogene geprüft. Ein
Treffer blockiert das Design nicht automatisch, sondern zeigt eine Warnung
mit Begründung, die der Nutzer explizit bestätigen muss, bevor er fortfahren
kann. Oben rechts im Header zeigt eine Statusanzeige neben dem
Dark-Mode-Button live an, ob der Screening-Service gerade erreichbar ist
("Biosecurity screening: on/off").

**Das ist standardmäßig AUS.** COMMEC braucht Conda und BLAST/HMMER — das
passt nicht ins schlanke Haupt-Image und wird nicht automatisch
mitinstalliert (anders als primer3-py/ViennaRNA). Ohne konfigurierten
Service läuft der Builder normal weiter, nur ohne dieses Screening (mit
einem sichtbaren Hinweis in Schritt 4).

**Datenbankumfang:** Das mitgelieferte `commec-service`-Image lädt beim
Build nur die kuratierte Biorisk+Low-concern-Datenbank (~1.2 GB) — nicht die
vollen Protein-/Nukleotid-Taxonomie-Datenbanken (zusammen über 1 TB laut
COMMEC-eigener Größenangabe), die auf den meisten Entwicklungsrechnern
weder auf die Platte passen noch in angemessener Zeit herunterladen. Das
bedeutet: kein Taxonomie-Bestmatch gegen beliebige Organismen, nur direkte
Treffer gegen die kuratierte Biorisk-Liste — Details und die Konsequenzen
davon (u. a. wie generische "Warning"-Ergebnisse für ungeprüfte, aber
harmlose Sequenzen gehandhabt werden) stehen in
[commec-service/README.md](commec-service/README.md).

Einrichten, wenn gewünscht — mit Docker Compose reicht ein Befehl, `app` und
`commec` finden sich automatisch über den Compose-internen Hostnamen
(`COMMEC_URL` in `docker-compose.yml` zeigt bereits standardmäßig auf
`http://commec:8787`):

```bash
docker compose --profile biosecurity up --build
```

Baut zusätzlich den `commec`-Container ([commec-service/](commec-service/))
mit der Biorisk-Datenbank — dauert beim ersten Mal ein paar Minuten
(Conda-Environment + ~1.2GB Download). Die Statusanzeige im Header schaltet
auf "on", sobald der Container bereit ist.

Bei lokaler Entwicklung ohne Docker (`pnpm dev`) stattdessen:

```bash
COMMEC_URL=http://localhost:8787 pnpm dev
```

(nachdem der `commec`-Container separat gestartet wurde, z. B. mit
`docker compose --profile biosecurity up commec`).

**Verifiziert:** Der komplette Ablauf (Container-Build, echter
`commec screen`-Aufruf, Frontend-Gate inkl. Warn-Modal) wurde end-to-end
gegen einen real gebauten und laufenden Container getestet — inklusive
eines positiven Tests mit einer echten, aus UniProt bezogenen
Conotoxin-Sequenz, die korrekt als "Flag" erkannt wurde und das Warn-Modal
auslöste. Details in [commec-service/README.md](commec-service/README.md).

## Encapsulin-Datenbank erweitern

Der Encapsulin-Filter (`/selector/`) liest seine Daten aus einzelnen JSON-Dateien
unter [encapsulin_selector/data/](encapsulin_selector/data/) — ein neues
Encapsulin hinzuzufügen heißt: Vorlage kopieren, Felder ausfüllen, `pnpm dev`
starten. Siehe [encapsulin_selector/data/README.md](encapsulin_selector/data/README.md).

# Permission
Some might encounter troubles while pushing it to the max. How weird.
