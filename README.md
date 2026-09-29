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

## Encapsulin-Datenbank erweitern

Der Encapsulin-Filter (`/selector/`) liest seine Daten aus einzelnen JSON-Dateien
unter [encapsulin_selector/data/](encapsulin_selector/data/) — ein neues
Encapsulin hinzuzufügen heißt: Vorlage kopieren, Felder ausfüllen, `pnpm dev`
starten. Siehe [encapsulin_selector/data/README.md](encapsulin_selector/data/README.md).

# Permission
Some might encounter troubles while pushing it to the max. How weird.
