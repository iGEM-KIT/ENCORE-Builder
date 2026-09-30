# Sequenz-Datenbank fuer Golden-Gate-Standardteile

Jedes Teil (Nanocompartment-Shell, Targeting-Peptid, Promotor, Linker,
Oberflaechen-Marker, NCS-Spacer, Terminator, Level-0/1/2-Ziel-Backbone oder
Cargo-Preset) ist eine eigene JSON-Datei, gruppiert nach Art in einem
Unterordner — genau wie bei `encapsulin_selector/data/` fuer die Encapsuline.
Um eine neue oder fehlende Sequenz einzutragen, sind KEINE Kenntnisse ueber
den Rest der Codebase noetig:

1. Die passende `_template.json` im jeweiligen Unterordner kopieren nach
   `<id>.json` (die `id` muss zum bestehenden Eintrag in
   `Biologik/level0_design/data.py` passen, z.B. `E-Tm` fuer die
   Thermotoga-maritima-Shell — siehe "Wie IDs zusammenhaengen" unten).
2. `sequence` ausfuellen, `sequence_status` von `"missing"` auf `"real"`
   setzen, `source` (woher die Sequenz stammt) ergaenzen.
3. Fertig — kein Python-Code aendern, kein Neustart noetig. `cli.py` wird pro
   Anfrage neu gestartet und liest die JSON-Dateien jedes Mal frisch von der
   Platte (anders als beim Selector gibt es hier keinen Build-Schritt zu
   einem generierten Bundle, weil das hier serverseitig in Python laeuft).

Sobald eine Sequenz auf `"real"` steht, verwendet `design.py` (`build_genbank`)
sie automatisch anstelle der bisherigen deterministischen Platzhalter-Sequenz
— die Source-Notiz im GenBank-Export wechselt dann von "deterministic
placeholder" zu "parts database (real sequence)".

## Wie IDs zusammenhaengen

Die "Katalog"-Listen in `data.py` (`NANOCOMPARTMENTS`, `LINKERS`,
`PROMOTERS`, `SURFACE_MARKERS`) bleiben die Quelle fuer IDs/Labels/UI-Metadaten
— nichts davon aendert sich. Diese Datenbank hier liefert nur, WENN vorhanden,
die zugehoerige echte Sequenz, nachgeschlagen ueber dieselbe ID:

| Katalog (`data.py`)                  | Feld            | Datenbank-Ordner            |
|---------------------------------------|-----------------|------------------------------|
| `NANOCOMPARTMENTS[i]`                 | `shell`         | `nanocompartment_shells/`   |
| `NANOCOMPARTMENTS[i]`                 | `tp`            | `targeting_peptides/`       |
| `LINKERS[i]`                          | `id`            | `linkers/`                  |
| `PROMOTERS[i]`                        | `id`            | `promoters/`                |
| `SURFACE_MARKERS[i]`                  | `id`            | `surface_markers/`          |
| (kein Katalog — ein generischer Spacer, siehe `design.py: placeholder_seq("NCS", 30)`) | — | `ncs_spacers/` (feste ID `standard`) |

`terminators/`, `level0_backbones/`, `level1_backbones/` und `level2_backbones/`
haben (noch) keinen Katalog in `data.py` — sie sind rein informationell aus
importierten GenBank-Dateien befuellt und noch nicht in die
Level-0/1/2-Design-Logik verdrahtet (siehe PROJECT_TODO.txt).

`cargo_presets/` ist die einzige Kategorie, die KEINE eigene Katalog-Liste in
`data.py` mehr hat — `CARGO_PRESETS` wird direkt aus dieser Datenbank gebaut
(siehe `data.py`).

## Gemeinsame Felder (fuer alle Ordner ausser den `level*_backbones/`-Ordnern)

- `id` — muss zum Katalog-Feld in `data.py` passen (siehe Tabelle oben).
- `kind` — Art des Teils, nur zur Selbstdokumentation.
- `label` — Anzeigename.
- `sequence` — die DNA-Sequenz, oder `null` solange sie fehlt.
- `sequence_status` — `"real"` oder `"missing"`. Nur bei `"real"` wird die
  Sequenz tatsaechlich verwendet (siehe oben).
- `on_stock` — `true`, `false` oder `null`, unabhaengig von `sequence_status`.
  Ein Teil kann fertig designt/sequenziert sein (`sequence_status: "real"`)
  und trotzdem physisch noch nicht im Kryo-Lager bei KIT liegen — z.B. ein
  selbst entworfener Linker oder Marker, der erst noch bestellt/synthetisiert
  werden muss. `true` = physisch auf Lager, `false` = designt, aber (noch)
  nicht auf Lager (muss bestellt/synthetisiert werden), `null` = noch nicht
  angegeben. Rein informativ fuer die Bestell-Checkliste in Schritt 4 — die
  Werte aller aktuellen Eintraege sind `null` und muessen noch nachgetragen
  werden (siehe PROJECT_TODO.txt).
- `length_bp` — bekannte/nominale Laenge in bp (aus `data.py`, z.B.
  `NOMINAL_BP`), auch wenn `sequence` noch `null` ist.
- `organism`, `source`, `notes` — Herkunft/Kontext, `null` falls unbekannt.
- `used_by` — welche `data.py`-Katalog-IDs auf diesen Eintrag verweisen (rein
  informativ, fuer Nachvollziehbarkeit).

## `level0_backbones/`, `level1_backbones/`, `level2_backbones/<id>.json`

Ein komplettes, zirkulaeres Plasmid-Backbone (z.B. aus einer GenBank-Datei
importiert) mit voller Sequenz, den kuratierten Kernfeldern (Marker, Origin,
Akzeptor-Overhangs `receiver_overhangs.5_prime`/`3_prime`, aktuell belegte
Stuffer-/Testkassette in `current_insert`) UND der vollstaendigen, roh
geparsten GenBank-`FEATURES`-Tabelle (`features`: Liste aus
`{type, location, qualifiers}`) fuer maximale Nachvollziehbarkeit. Hat
ebenfalls das `on_stock`-Feld (siehe oben) direkt nach `sequence_status`.

Aktuell real hinterlegt: `pAGM9121-lvl0-dest` (Level 0, Weber et al. 2011),
`pAGM1311-lvl1-dest` (Level 1, Weber et al. 2011), `pESC-HIS-lvl2-dest`
(Level 2, vom Nutzer bereitgestelltes pESC-HIS). Alle drei stammen aus vom
Nutzer bereitgestellten GenBank-Dateien, nicht selbst generiert.

## Validierung

`load_parts()` (`parts_db.py`) bricht mit einer klaren Fehlermeldung ab (statt
still eine kaputte Datenbank zu laden), wenn eine `id` in einem Ordner fehlt
oder doppelt vergeben ist, oder eine Datei kein gueltiges JSON ist.
