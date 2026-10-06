# Sequenz-Datenbank fuer Golden-Gate-Standardteile

Jeder Eintrag ist eine eigene JSON-Datei, gruppiert nach Art in einem Unterordner — genau wie bei
`encapsulin_selector/data/` fuer die Encapsuline. Eine neue oder geaenderte Datei wirkt sofort (kein Build, kein Neustart):
`cli.py` wird pro Anfrage neu gestartet und liest die Dateien jedes Mal frisch von der Platte.

| Ordner              | Inhalt |
|---------------------|--------|
| `level0_inserts/`   | die reine Teilsequenz je Level-0-Plasmid: Shells, Cargos, Linker, Marker, Intein, Targeting-Peptide, NCS (siehe unten) |
| `promoters/`        | Promotoren (Sequenz noch nicht hinterlegt -> Platzhalter) |
| `terminators/`      | Terminatoren, rein informativ |
| `level0_backbones/`, `level1_backbones/`, `level2_backbones/` | die Ziel-Backbones pAGM9121, pAGM1311, pESC-HIS |
| `type_overhangs/`   | die sieben Overhang-Adapter (Quelle der Overhangs und des Frame-Spacers) |

Die Dropdowns der Software (Katalog-Metadaten wie Labels, T-Zahl, Beschreibung) stehen in `data.py`; welche Teile es an
welcher Site und welchem Slot wirklich gibt und welche Sequenz sie haben, kommt aus `level0_inserts/`.

## `level0_inserts/<id>.json`

Pro Level-0-Plasmid eine Datei, `id` = Beschreibung im GenBank-File (z.B. `Lvl0.2_b_034`). Gespeichert ist NUR das Insert —
nicht das Plasmid, ohne Type-Overhangs und ohne den Frame-Spacer des Plasmids; beides setzt die Software aus
`type_overhangs/` wieder an. `sequence` ist immer die Sense-Sequenz des Teils (wie es abgelesen wird); liegt es im Plasmid
revers-komplementiert (Cargo Site), ist das hier schon zurueckgedreht — die Software dreht das Cargo-Modul beim Bauen wieder.

- `plasmid_name`, `label` — Name im GenBank-File bzw. in `Level 0 constructs.xlsx`.
- `category` — `shell`, `cargo`, `linker`, `marker`, `intein`, `tp` oder `ncs`; `part` / `part_label` — die Teil-ID und das
  Label in den Dropdowns (z.B. Linker `L3` = `GSSS3`).
- `type_slot` (1-5) und `site` (`nc_site` / `cargo_site`). Die Site folgt bei Type 0.1/0.5 aus dem Level-2-Overhang
  (`level2_overhang`: TGAT/AATG = NC Site, CCAA/CGTT = Cargo Site), bei Type 0.2-0.4 aus dem Strang, auf dem das Teil im
  Plasmid liegt (`stored_orientation`: sense = NC Site, antisense = Cargo Site; die "rc"-Plasmide).
- `variant` (`tp`: `c_term` = Type 0.1 mit Stopcodon, `n_term` = Type 0.5 mit Startcodon) und `ncs_role` (`plain` / `stop`;
  `stop` nur an den Slots hinter dem Mittelteil: NC Site 0.4/0.5, Cargo Site 0.2/0.1).
- `frame_spacer_in_plasmid` — die 2 Basen, die das Plasmid vor dem ORF traegt (nur zur Nachvollziehbarkeit; sie sind hier
  NICHT in `sequence` enthalten, die Software setzt ihren eigenen Spacer aus den Adaptern).
- `on_stock` — `true` = Glycerinstock vorhanden (Spalte "Glycerol" in `Level 0 constructs.xlsx`: ja), `false` = nein.
- `checks` — Laenge durch 3 teilbar, Start-/Stopcodon, BsaI-/BbsI-Stellen im Teil.
- `notes` — Auffaelligkeiten, die beim Import aufgefallen sind (zu pruefen).

Die Dropdowns bieten ein Teil nur dort an, wo es ein Level-0-Plasmid dafuer gibt (`slots` je Bibliothek in
`get_libraries()`); die Teile selbst sind unabhaengig davon verwendbar (Fallback auf die Sequenz derselben Teil-ID von einem
anderen Slot, Lagerstatus dann `false`).

## Gemeinsame Felder (promoters/, terminators/)

- `id`, `kind`, `label`, `sequence` (oder `null`), `sequence_status` (`real`/`missing`), `on_stock`, `length_bp`,
  `organism`, `source`, `notes`, `used_by`.

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

## `type_overhangs/<id>.json`

Die sieben Overhang-Adapter, die an die Sequenz jedes Level-0-Teils angehaengt werden
(BbsI-Schnittstelle, Level-0-Overhangs 0N/0C passend zum Level-0-Backbone, Level-1-Overhangs
fuer den jeweiligen Type-Slot und bei Type 0.1/0.5 zusaetzlich die Level-2-Overhangs, um einen
4-nt-"Insert"-Platzhalter herum). Die CDS bzw. Teilsequenz ersetzt diesen Platzhalter. Eine
Datei pro Adapter, Dateiname = `id` = Name im GenBank-File des Nutzers:

| id      | Type-Slot | `used_for_modules`        | Besonderheit |
|---------|-----------|---------------------------|--------------|
| `0.1`   | 0.1       | `nc_site`                 | Level-2-Overhang `2_N` = TGAT |
| `0.1rc` | 0.1       | `cargo_site`              | Level-2-Overhang `2_N` = CCAA (Cargo-Modul, rc-Variante) |
| `0.2`   | 0.2       | `nc_site`, `cargo_site`   | beide Seiten |
| `0.3`   | 0.3       | `nc_site`, `cargo_site`   | beide Seiten |
| `0.4`   | 0.4       | `nc_site`, `cargo_site`   | beide Seiten |
| `0.5`   | 0.5       | `nc_site`                 | Level-2-Overhang `2_C` = AATG |
| `0.5rc` | 0.5       | `cargo_site`              | Level-2-Overhang `2_C` = CGTT (Cargo-Modul, rc-Variante) |

Felder (zusaetzlich zu `id`/`kind`/`label`/`sequence`/`sequence_status`/`on_stock`/
`length_bp`/`source`/`notes`/`used_by`, siehe oben):

- `type_slot` — 1..5 (Type 0.x).
- `used_for_modules` — Liste aus `"nc_site"` (Nanocompartment-Site) und/oder `"cargo_site"`.
- `reverse_complement_variant` — `true` bei den `rc`-Adaptern der Cargo Site (Antisense-Modul).
- `description` — DEFINITION-Zeile aus dem GenBank-File.
- `enzyme`, `bbsi_sites` — Erkennungsstellen (`GAAGAC` bzw. rc) mit Position/Strang.
- `overhangs` — Liste der beschrifteten Overhangs: `label` (z.B. `0.5N Lvl1`), `role`
  (`level0_N`, `level1_N`, `level2_N`, `level1_C`, `level2_C`, `level0_C`), `location`, `strand`,
  `sequence_top_strand` (Basen auf dem Top-Strang) und `sequence_own_strand_5to3` (so wie auf
  dem eigenen Strang gelesen, also bei `strand: "-"` das Reverse-Komplement).
- `insert` — Position und Platzhalter (`AAAA`) der Stelle, an der die CDS eingesetzt wird.
- `frame_spacer` — 2 nt (`GC`) direkt vor dem Insert (5'-Seite, Top-Strand), hinter dem Level-1-N-Overhang und damit
  INNERHALB des BsaI-Fragments (wird beim Klonieren nicht herausgeschnitten). Der 4-nt-Overhang zwischen zwei Teilen
  allein verschiebt das Leseraster um 1 nt; Overhang (4) + Spacer (2) = 6 nt = zwei Codons, fusionierte Teile bleiben im
  Raster. Gewaehlt so, dass in beiden Leserichtungen (Sense- und Cargo-Modul, das antisense liegt) kein Stopcodon an
  der Naht entsteht und keine BsaI-/BbsI-Stelle neu gebildet wird (Test: `test_junction_codons_are_never_stops_...`).
- `features` — die komplette, roh geparste GenBank-Feature-Tabelle.

Stand: Die Overhangs der Adapter waren gegen die frueheren hartcodierten Konstanten gegengeprueft (Level-1-Overhangs
je Slot, NC-Flanken TGAT/TTAC, Cargo-Flanken CCAA/GCAA — rechter Wert jeweils als Komplement); die Adapter sind jetzt
die Quelle dafuer. Nicht belegt: die Promotor-Flanke ACTA.

## Validierung

`load_parts()` (`parts_db.py`) bricht mit einer klaren Fehlermeldung ab (statt
still eine kaputte Datenbank zu laden), wenn eine `id` in einem Ordner fehlt
oder doppelt vergeben ist, oder eine Datei kein gueltiges JSON ist.
