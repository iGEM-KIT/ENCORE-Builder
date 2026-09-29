# commec-service

Optionaler Sidecar-Container, der [COMMEC](https://github.com/ibbis-bio/common-mechanism)
("Common Mechanism", IBBIS) per HTTP nutzbar macht. commec selbst ist eine
FASTA-in/JSON-out-CLI ohne eigene API — `app.py` ist ein dünner Wrapper
darum, damit `server/utils/commec.js` (im Hauptprojekt) es per HTTP aufrufen
kann.

Warum ein eigener Container statt Teil des Haupt-Images: commec braucht
Conda und BLAST/HMMER — das ist zu schwer, um es wie primer3-py/ViennaRNA
automatisch mitzuinstallieren. Details und Einrichtung: siehe die Sektion
"Biosecurity screening" in der [Haupt-README](../README.md).

## Datenbankumfang (wichtig!)

Dieses Image lädt beim Build **nur** die kuratierte Biorisk+Low-concern-Datenbank
(~1.2 GB, per `commec setup` mit einer festen Antwortsequenz, siehe
`Dockerfile`) — **nicht** die vollen Taxonomie-Datenbanken (Protein-NR
~530GB, Nukleotid-NT ~580GB; `commec setup -a` würde ALLES laden, zusammen
über 1TB). Das war eine bewusste Entscheidung: die vollen Datenbanken passen
auf den meisten Entwicklungsrechnern nicht auf die Platte und brauchen sehr
lange zum Laden.

Praktische Folge: `commec screen` läuft hier immer mit `--skip-tx --skip-nt`
(`app.py`, steuerbar über `COMMEC_SKIP_TAXONOMY`). Damit liefert commec
**keine Taxonomie-Bestmatches** gegen beliebige Organismen — nur direkte
Sequenztreffer gegen die kuratierte Biorisk-Liste (bekannte Toxine,
Virulenzfaktoren, regulierte Pathogene). Ein wichtiger Nebeneffekt: **jede**
Sequenz ohne Treffer bekommt von commec selbst `screen_status: "Warning"`
mit der Begründung "Sequence risk is unknown, possibly generated in
silico." — auch völlig harmlose Gene wie GFP, weil ohne Taxonomie-Check
nichts *positiv* als sicher bestätigt werden kann. Das ist erwartetes
commec-Verhalten bei einem unvollständigen Datenbanksatz, kein Fehler.

Deshalb wertet das Frontend (`frontend/index.html`, `biosecEffectiveStatus()`)
in diesem Fall gezielt das `biorisk`-Feld statt des generischen
`screen_status` aus — nur ein echter Biorisk-Treffer (`biorisk` != `Pass`)
löst die Warnung/Blockierung aus, nicht das allgemeine "ungeprüft"-Warning.

## Endpunkte

- `GET /health` — `{"ok": bool, "detail": str}`. `ok` ist `false`, solange
  `COMMEC_DB_DIR` (Standard `/databases`) fehlt oder leer ist.
- `POST /screen` — Body `{"sequences": [{"label": str, "sequence": str}]}`,
  Antwort `{"results": [...]}` mit einem Eintrag pro Eingabesequenz, in
  derselben Reihenfolge:
  - Erfolg: `{"available": true, "status": {"screen_status": "Pass"|"Warning"|"Flag"|"Mixed"|"Error"|"Skip", "biorisk": ..., "protein_taxonomy": ..., "nucleotide_taxonomy": ..., "low_concern": ..., "rationale": "..."}}`
    (das `status`-Objekt kommt unverändert von commec selbst)
  - Fehlgeschlagen (Sequenz zu lang, commec-Fehler, Timeout, ...):
    `{"available": false, "reason": "..."}`

Jede Sequenz läuft als eigener `commec screen`-Aufruf in einem temporären
Verzeichnis (unabhängig voneinander — ein Fehler bei einer Sequenz blockiert
nicht die anderen im selben Batch).

## Konfiguration (Umgebungsvariablen)

- `COMMEC_DB_DIR` (Standard `/databases`) — wohin `commec setup` geladen hat.
- `COMMEC_THREADS` (Standard `4`) — an `commec screen -t` durchgereicht.
- `COMMEC_SKIP_TAXONOMY` (Standard `true`) — haengt `--skip-tx --skip-nt` an.
  Nur auf `false` setzen, wenn dieses Image um die Protein-/Nukleotid-Taxonomie-
  Datenbanken erweitert wurde (siehe oben).
- `COMMEC_RUN_TIMEOUT_SECONDS` (Standard `900`) — harter Timeout pro
  Einzel-Screen, damit eine hängende Sequenz nicht den ganzen Service blockiert.
- `COMMEC_MAX_SEQ_LEN` (Standard `20000`) — Sequenzen darüber werden ohne
  commec-Aufruf mit `available:false` abgelehnt.
- `PORT` (Standard `8787`).

## Verifiziert

Dieser Wrapper wurde gegen einen echten, lokal gebauten Container
(commec 1.0.4) end-to-end getestet, nicht nur nach Doku gebaut:

- `commec setup` mit der in `Dockerfile` verwendeten Antwortsequenz lädt
  tatsächlich nur `biorisk/` + `low_concern/` (~1.2 GB) herunter.
- `GET /health` meldet `ok: true` sobald die Datenbank da ist.
- `POST /screen` mit einer harmlosen Sequenz (GFP) liefert
  `biorisk: "Pass"` (bei generischem `screen_status: "Warning"`, siehe oben).
- `POST /screen` mit einer echten, aus UniProt bezogenen Conotoxin-Sequenz
  (Q9BPJ4, in der Biorisk-Datenbank als "Must flag" gelistet) liefert
  korrekt `screen_status: "Flag"`, `biorisk: "Flag"`,
  `rationale: "Matches sequence with pathogenic or toxin function."` — und
  loest im Frontend zuverlaessig das blockierende Warn-Modal aus.
