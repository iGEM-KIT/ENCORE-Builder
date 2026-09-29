# Encapsulin-Datenbank fuer den Selector

Jedes Encapsulin ist eine eigene JSON-Datei. Um einen neuen Kandidaten
hinzuzufuegen, sind KEINE Kenntnisse ueber den Rest der Codebase noetig —
nur diese drei Schritte:

1. `candidates/_template.json` kopieren nach `candidates/<DEINE_ID>.json`
   (z.B. der UniProt-Accession, wie bei allen bestehenden Eintraegen: `Q1D6H4.json`).
2. Felder ausfuellen. Unbekannte Felder einfach auf `null` lassen — die
   bestehenden 74 Eintraege haben das an vielen Stellen auch so.
3. Optional: eine oder mehrere gemessene Assemblies in `assemblies/` ergaenzen
   (siehe unten), dann in der Kandidaten-Datei `reference_assembly_id` auf die
   wichtigste davon setzen.

Danach `pnpm dev` starten (baut `selector-data.js` automatisch neu) und im
Filter unter `/selector/` pruefen, ob der neue Eintrag auftaucht. Bei einer
Pull Request die neu gebaute `encapsulin_selector/selector-data.js` mit
einchecken (falls vergessen, holt ein Maintainer das mit
`pnpm build:selector-data` nach).

**`selector-data.js` selbst nie von Hand editieren** — die Datei wird aus
diesem Ordner generiert (siehe `scripts/build-selector-data.mjs`) und beim
naechsten Build ueberschrieben.

## candidates/<ID>.json

Ein Eintrag pro Protein/UniProt-Eintrag. Direkt fuer die Suche/Filter im
Selector genutzt: `candidate_id`, `entry_name`, `protein_name`, `organism`,
`genus`, `strain`, `gene`, `locus_tag`, `orf_name`, `encapsulin_family`,
`reference_assembly_id`. `source_uniprot` wird als Link hinter dem
`candidate_id` in der Kandidaten-Karte angezeigt, falls gesetzt — bei einer
echten UniProt-Accession als `candidate_id` also einfach
`https://www.uniprot.org/uniprotkb/<candidate_id>/entry` eintragen. Der Rest
sind Kuratierungs-Metadaten (Quellen, Vertrauenslevel, Notizen) — nuetzlich,
aber optional/`null`, falls unbekannt.

`assembly_count` gehoert NICHT in diese Datei — das zaehlt der Build-Schritt
automatisch aus den passenden Dateien in `assemblies/`.

## assemblies/<ID>.json

Eine gemessene/beobachtete Kapsid-Variante (z.B. ein bestimmter T-Number-Zustand)
zu einem Kandidaten, verknuepft ueber `candidate_id`. Ein Kandidat kann mehrere
Assemblies haben (z.B. T=1 und T=3). `shell_diameter_nm` darf eine Zahl
(`24`), ein Naeherungswert (`"~24"`) oder ein Bereich (`"20-24"`) sein — der
Build-Schritt wandelt das automatisch in die intern genutzte Min/Max/Mitte-Form
um, dafuer muss hier nichts weiter ausgefuellt werden.

Eine Assembly hat KEINEN eigenen UniProt-Eintrag (UniProt indiziert
Proteinsequenzen, nicht einzelne experimentelle Strukturen oder Mutanten) —
stattdessen wird `structure_id` als Link zur jeweiligen RCSB-PDB-Seite
angezeigt, falls gesetzt. Mehrere PDB-Codes durch Semikolon trennen
(`"4PT2; 7S20"`), jeder wird einzeln verlinkt.

## meta.json

Allgemeine Beschreibung der Datenbank (Titel, Quelle, Hinweistexte). Die
Zaehler (`candidate_count`, `assembly_count`, ...) gehoeren nicht hier rein,
die berechnet der Build-Schritt selbst.

## Validierung

`pnpm build:selector-data` bricht mit einer klaren Fehlermeldung ab, wenn:

- eine `candidate_id`/`assembly_id` doppelt vergeben wurde,
- eine Assembly auf eine nicht existierende `candidate_id` verweist,
- ein Kandidat mit `reference_assembly_id` auf eine nicht existierende
  Assembly verweist.
