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
automatisch per [COMMEC v2](https://github.com/ibbis-bio/common-mechanism)
("Common Mechanism", IBBIS) auf Treffer gegen regulierte Pathogene oder
bekannte Virulenzfaktoren geprüft. Ein Treffer blockiert das Design nicht
automatisch, sondern zeigt eine Warnung mit Begründung, die der Nutzer
explizit bestätigen muss, bevor er fortfahren kann (ein "Warning" kann ein
gutartiges, geteiltes Sequenzmotiv sein — siehe Begründungstext pro Treffer).

**Das ist standardmäßig AUS.** COMMEC braucht Conda, BLAST/HMMER und ~40GB
Referenzdatenbanken (~7-8GB Download) — das passt nicht ins schlanke
Haupt-Image und wird nicht automatisch mitinstalliert (anders als
primer3-py/ViennaRNA). Ohne konfigurierten Service läuft der Builder normal
weiter, nur ohne dieses Screening (mit einem sichtbaren Hinweis in Schritt 4).

Einrichten, wenn gewünscht:

```bash
docker compose --profile biosecurity up --build
```

Das baut zusätzlich den `commec`-Container ([commec-service/](commec-service/))
mit den vollen Referenzdatenbanken — der erste Build dauert entsprechend
lange (grosser Download). Danach der Haupt-App sagen, wo der Service läuft:

```bash
COMMEC_URL=http://localhost:8787 pnpm dev
```

(oder `COMMEC_URL=http://commec:8787` als Umgebungsvariable für den `app`-Service
in `docker-compose.yml`, wenn beide Container zusammen laufen). Ein einzelner
COMMEC-Lauf kann laut IBBIS-Dokumentation von Sekunden bis zu mehreren
Minuten dauern — das ist erwartet, siehe `COMMEC_RUN_TIMEOUT_SECONDS` in
[commec-service/app.py](commec-service/app.py).

**Hinweis zur Testabdeckung:** Der `commec-service`-Wrapper wurde gegen die
öffentliche COMMEC-Dokumentation gebaut (CLI-Flags, JSON-Schema), konnte in
dieser Umgebung aber mangels Netzwerkzugriff auf die ~40GB-Datenbanken nicht
gegen einen echten `commec screen`-Lauf getestet werden. Vor dem produktiven
Einsatz einmal mit einer bekannten Testsequenz (z. B. aus den
[commec-examples](https://github.com/ibbis-bio/common-mechanism/wiki/Tutorial))
verifizieren.

## Encapsulin-Datenbank erweitern

Der Encapsulin-Filter (`/selector/`) liest seine Daten aus einzelnen JSON-Dateien
unter [encapsulin_selector/data/](encapsulin_selector/data/) — ein neues
Encapsulin hinzuzufügen heißt: Vorlage kopieren, Felder ausfüllen, `pnpm dev`
starten. Siehe [encapsulin_selector/data/README.md](encapsulin_selector/data/README.md).

# Permission
Some might encounter troubles while pushing it to the max. How weird.
