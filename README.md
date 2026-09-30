# ENCORE-Builder

Golden Gate Design Software, um mit unserer Golden Gate Toolbox einen
Encapsulin-Cargo-Konstrukt zu planen: Nanocompartment und Cargo zusammenstellen,
Primer und eine fertige Level-2-Plasmidkarte bekommen — inklusive einem
separaten Filter-Tool, um das passende Encapsulin zu finden.

## Schnellstart — Software einfach benutzen

Du brauchst nur [Docker](https://www.docker.com/products/docker-desktop/)
installiert. Keine Programmierkenntnisse, kein Node.js, kein Python nötig.

1. Repo herunterladen:
   ```bash
   git clone https://github.com/iGEM-KIT/ENCORE-Builder.git
   cd ENCORE-Builder
   ```
2. Starten:
   ```bash
   docker compose up --build
   ```
   Der erste Start dauert etwas länger (baut den Builder und lädt zusätzlich
   die ~1,2GB-Datenbank für das automatische Biosicherheits-Screening
   herunter, siehe unten).
3. Im Browser öffnen: **[http://localhost:3000](http://localhost:3000)**
4. Zum Beenden im Terminal `Ctrl+C` drücken, oder in einem neuen Terminal:
   ```bash
   docker compose down
   ```

Das war's — der Builder und der Encapsulin-Filter laufen jetzt vollständig.

### Biosicherheits-Screening ist immer dabei

Jede selbst eingegebene Gensequenz wird automatisch auf bekannte Toxine,
Virulenzfaktoren und regulierte Pathogene geprüft
([COMMEC](https://github.com/ibbis-bio/common-mechanism) von IBBIS) — dafür
startet `docker compose up` standardmäßig einen zweiten Container mit, ohne
dass dafür etwas extra angegeben werden muss. Sobald beide Container laufen,
zeigt der Header oben rechts **"Biosecurity screening: on"** mit einem
grünen Punkt.

## Die Software benutzen

1. Startseite → **"Start builder"**
2. **Schritt 1 – Nanocompartment Site:** Nanocompartment aus der Bibliothek
   wählen (oder eine eigene Sequenz einfügen) und die vier Module drumherum
   belegen (Spacer, Linker, Oberflächenmarker oder eigene Sequenz)
3. **Schritt 2 – Cargo Site:** eigene CDS einfügen (oder ein Beispiel wie GFP
   laden) und die Module drumherum belegen
4. **Schritt 3 – Promoter:** Promoter auswählen
5. **"Calculate construct"** klicken — läuft bei aktivem Screening automatisch
   mit; nur bei einem echten Treffer erscheint eine Warnung, die man vor dem
   Fortfahren bestätigen muss
6. **Schritt 4 – Ergebnis:** fertiges Golden-Gate-Design (Level 0 → 1 → 2),
   Primer, Plasmidkarte und Bestellliste, als annotierte GenBank-Datei (.gb)
   exportierbar

Passendes Encapsulin noch nicht klar? Oben im Header auf **"Encapsulin
Filter"** wechseln — dort lässt sich nach Organismus/Accession suchen oder
nach physikalischen Eigenschaften (Durchmesser, Triangulationszahl) filtern.

---

## Für Entwickler

### Lokale Entwicklung (ohne Docker)

Voraussetzung: Node.js ≥20.19 und [pnpm](https://pnpm.io/).

```bash
pnpm install
pnpm dev
```

`pnpm dev` legt beim ersten Start automatisch ein `.venv` mit primer3-py an
([scripts/setup-python.mjs](scripts/setup-python.mjs)) — kein manuelles
`pip install` nötig. Ist kein Python 3 im PATH oder schlägt die Installation
fehl (z. B. fehlender C-Compiler), läuft Biologik trotzdem weiter, nur mit
einer ungenaueren Wallace-Tm-Schätzung statt primer3. Einen bestimmten
Interpreter erzwingen geht über `BIOLOGIK_PYTHON=/pfad/zu/python`.

Alternativ Docker ohne Compose:

```bash
docker build -t encore-builder .
docker run -p 3000:3000 encore-builder
```

### Biosicherheits-Screening (COMMEC) — Details

Bevor der Builder in Schritt 4 das finale Design berechnet, wird jede vom
Nutzer selbst eingegebene Sequenz (Cargo, eigene Shell, eigene Modul-Teile)
per COMMEC auf Treffer gegen eine kuratierte Liste bekannter Toxine,
Virulenzfaktoren und regulierter Pathogene geprüft. Ein Treffer blockiert das
Design nicht automatisch, sondern zeigt eine Warnung mit Begründung, die der
Nutzer explizit bestätigen muss, bevor er fortfahren kann.

**Läuft standardmäßig als zweiter Container mit**, weil COMMEC Conda und
BLAST/HMMER braucht — das passt nicht ins schlanke Haupt-Image und wird nicht
automatisch mitinstalliert (anders als primer3-py/ViennaRNA), deshalb der
eigene Sidecar-Container statt eines eingebauten Checks. Bewusst kein reines
Opt-in mehr: ein Sicherheits-Check, den man erst manuell dazuschalten müsste,
würde im Alltag zu leicht vergessen oder übersprungen. Ist `commec` einmal
nicht erreichbar (z. B. während des Hochfahrens, oder bei `COMMEC_URL`
manuell auf leer gesetzt), läuft der Builder trotzdem normal weiter, nur ohne
dieses Screening (mit sichtbarem Hinweis in Schritt 4) — echte
Unumgehbarkeit kann selbst gehostete, quelloffene Software ohnehin nicht
garantieren, das ist hier also die ehrliche Grundeinstellung, kein
Manipulationsschutz.

**Datenbankumfang:** Das mitgelieferte `commec-service`-Image lädt beim Build
nur die kuratierte Biorisk+Low-concern-Datenbank (~1.2 GB) — nicht die vollen
Protein-/Nukleotid-Taxonomie-Datenbanken (zusammen über 1 TB laut
COMMEC-eigener Größenangabe), die auf den meisten Rechnern weder auf die
Platte passen noch in angemessener Zeit herunterladen. Das bedeutet: kein
Taxonomie-Bestmatch gegen beliebige Organismen, nur direkte Treffer gegen die
kuratierte Biorisk-Liste — Details und Konsequenzen (u. a. wie generische
"Warning"-Ergebnisse für ungeprüfte, aber harmlose Sequenzen gehandhabt
werden) stehen in [commec-service/README.md](commec-service/README.md).

Mit Docker Compose finden sich `app` und `commec` automatisch über den
Compose-internen Hostnamen (`COMMEC_URL` in `docker-compose.yml` zeigt
standardmäßig auf `http://commec:8787`). Bei lokaler Entwicklung ohne Docker:

```bash
COMMEC_URL=http://localhost:8787 pnpm dev
```

(nachdem der `commec`-Container separat gestartet wurde, z. B. mit
`docker compose up commec`).

**Verifiziert:** Der komplette Ablauf (Container-Build, echter
`commec screen`-Aufruf, Frontend-Gate inkl. Warn-Modal) wurde end-to-end
gegen einen real gebauten und laufenden Container getestet — inklusive eines
positiven Tests mit einer echten, aus UniProt bezogenen Conotoxin-Sequenz,
die korrekt als "Flag" erkannt wurde und das Warn-Modal auslöste.

### Encapsulin-Datenbank erweitern

Der Encapsulin-Filter (`/selector/`) liest seine Daten aus einzelnen
JSON-Dateien unter [encapsulin_selector/data/](encapsulin_selector/data/) —
ein neues Encapsulin hinzuzufügen heißt: Vorlage kopieren, Felder ausfüllen,
`pnpm dev` starten. Siehe
[encapsulin_selector/data/README.md](encapsulin_selector/data/README.md).

# Permission
Some might encounter troubles while pushing it to the max. How weird.
