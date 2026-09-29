# commec-service

Optionaler Sidecar-Container, der [COMMEC v2](https://github.com/ibbis-bio/common-mechanism)
("Common Mechanism", IBBIS) per HTTP nutzbar macht. commec selbst ist eine
FASTA-in/JSON-out-CLI ohne eigene API — `app.py` ist ein dünner Wrapper
darum, damit `server/utils/commec.js` (im Hauptprojekt) es per HTTP aufrufen
kann.

Warum ein eigener Container statt Teil des Haupt-Images: commec braucht
Conda, BLAST/HMMER und ~40GB Referenzdatenbanken (~7-8GB Download) — das ist
zu schwer, um es wie primer3-py/ViennaRNA automatisch mitzuinstallieren.
Details und Einrichtung: siehe die Sektion "Biosecurity screening" in der
[Haupt-README](../README.md).

## Endpunkte

- `GET /health` — `{"ok": bool, "detail": str}`. `ok` ist `false`, solange
  `COMMEC_DB_DIR` (Standard `/databases`) fehlt oder leer ist, also bevor
  `commec setup` erfolgreich lief.
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
- `COMMEC_RUN_TIMEOUT_SECONDS` (Standard `900`) — harter Timeout pro
  Einzel-Screen, damit eine hängende Sequenz nicht den ganzen Service blockiert.
- `COMMEC_MAX_SEQ_LEN` (Standard `20000`) — Sequenzen darüber werden ohne
  commec-Aufruf mit `available:false` abgelehnt.
- `PORT` (Standard `8787`).

## Bekannte Einschränkung

Dieser Wrapper wurde anhand der öffentlichen COMMEC-Doku (CLI-Referenz,
Beispiel-Output im Wiki) gebaut, aber **nicht gegen einen echten
`commec screen`-Lauf getestet** — die Entwicklungsumgebung hatte keinen
Zugriff, um die ~40GB Referenzdatenbanken herunterzuladen. `_find_status()`
in `app.py` durchsucht das JSON-Ergebnis deshalb defensiv nach einem Objekt
mit einem `screen_status`-Feld, statt sich starr auf eine vermutete
Verschachtelung zu verlassen — trotzdem vor dem produktiven Einsatz einmal
mit einer bekannten Testsequenz verifizieren (z. B. eine der
[commec-examples](https://github.com/ibbis-bio/common-mechanism/wiki/Tutorial)).
