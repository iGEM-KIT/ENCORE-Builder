from __future__ import annotations

"""Loader fuer Biologik/level0_design/parts/: die Sequenz-Datenbank fuer
Golden-Gate-Standardteile (Level-0-Inserts: Shells, Cargos, Linker, Marker, TPs, NCS-Spacer;
Promotoren, Terminatoren, Level-0/1/2-Ziel-Backbones, Type-Overhang-Adapter).

Gleiches Prinzip wie encapsulin_selector/data/ (eine JSON-Datei pro Eintrag,
gruppiert nach Art in Unterordnern); siehe parts/README.md. Anders als beim
Selector gibt es hier KEINEN Build-Schritt zu einem generierten JS-Bundle:
das laeuft serverseitig in Python (cli.py wird pro Request neu gestartet),
daher werden die JSON-Dateien bei jedem Aufruf frisch von der Platte gelesen; eine neue/geaenderte Datei wirkt sofort, ohne Neustart oder Build.
"""

import json
from pathlib import Path

PARTS_ROOT = Path(__file__).parent / "parts"

KINDS = [
    "level0_inserts",
    "promoters",
    "terminators",
    "level0_backbones",
    "level1_backbones",
    "level2_backbones",
    "type_overhangs",
]


def _read_kind(kind: str) -> list[dict]:
    directory = PARTS_ROOT / kind
    if not directory.is_dir():
        return []
    entries = []
    seen_ids = set()
    for path in sorted(directory.glob("*.json")):
        if path.name.startswith("_"):
            continue  # Vorlagen (z.B. _template.json) fliessen nicht mit ein.
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError(f"parts/{kind}/{path.name} ist kein gueltiges JSON: {error}") from error
        entry_id = entry.get("id")
        if not entry_id:
            raise ValueError(f"parts/{kind}/{path.name} hat kein \"id\"-Feld.")
        if entry_id in seen_ids:
            raise ValueError(f"parts/{kind}: id \"{entry_id}\" kommt doppelt vor (zuletzt in {path.name}).")
        seen_ids.add(entry_id)
        entries.append(entry)
    return entries


def load_parts() -> dict:
    """{kind: [entries...]} fuer jeden parts/-Unterordner."""
    return {kind: _read_kind(kind) for kind in KINDS}


def find_part(kind: str, part_id: str) -> dict | None:
    return next((e for e in _read_kind(kind) if e.get("id") == part_id), None)


def find_real_sequence(kind: str, part_id: str) -> str | None:
    """Liefert die echte Sequenz eines Teils, falls in der Datenbank hinterlegt
    (sequence_status == "real" und sequence gesetzt) — sonst None, damit der
    Aufrufer auf die deterministische Platzhalter-Sequenz zurueckfallen kann."""
    entry = find_part(kind, part_id)
    if not entry:
        return None
    seq = entry.get("sequence")
    if not seq or entry.get("sequence_status") != "real":
        return None
    return seq


def inserts() -> list[dict]:
    """Alle Level-0-Inserts (parts/level0_inserts/): die reine Teilsequenz je Level-0-Plasmid, ohne Overhangs und ohne Frame-Spacer."""
    return _read_kind("level0_inserts")


def find_inserts(category: str, part: str | None = None, site: str | None = None, slot: int | None = None,
                 **extra) -> list[dict]:
    """Inserts einer Kategorie (shell, cargo, linker, marker, intein, tp, ncs), optional gefiltert nach Teil-ID,
    Site ("nc_site"/"cargo_site"), Type-Slot und weiteren Feldern (variant="c_term", ncs_role="stop", ...)."""
    out = []
    for entry in inserts():
        if entry.get("category") != category:
            continue
        if part is not None and entry.get("part") != part:
            continue
        if site is not None and entry.get("site") != site:
            continue
        if slot is not None and entry.get("type_slot") != slot:
            continue
        if any(entry.get(key) != value for key, value in extra.items()):
            continue
        out.append(entry)
    return out
