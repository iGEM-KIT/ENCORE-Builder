"""Loader for Biologik/level0_design/parts/: the sequence database for
Golden Gate standard parts (Level 0 inserts: shells, cargos, linkers, markers, TPs, NCS spacers;
promoters, terminators, Level 0/1/2 destination backbones, Type overhang adapters).

Same principle as encapsulin_selector/data/ (one JSON file per entry,
grouped by kind in subfolders); see parts/README.md. Unlike the
selector there is NO build step to a generated JS bundle:
this runs server side in Python (cli.py is restarted per request),
so the JSON files are read fresh from disk on every call; a new or changed file takes effect immediately, without restart or build.
"""

from __future__ import annotations


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
            continue  # Templates (e.g. _template.json) are not included.
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError(f"parts/{kind}/{path.name} is not valid JSON: {error}") from error
        entry_id = entry.get("id")
        if not entry_id:
            raise ValueError(f"parts/{kind}/{path.name} has no \"id\" field.")
        if entry_id in seen_ids:
            raise ValueError(f"parts/{kind}: id \"{entry_id}\" occurs twice (last in {path.name}).")
        seen_ids.add(entry_id)
        entries.append(entry)
    return entries


def load_parts() -> dict:
    """{kind: [entries...]} for every parts/ subfolder."""
    return {kind: _read_kind(kind) for kind in KINDS}


def find_part(kind: str, part_id: str) -> dict | None:
    return next((e for e in _read_kind(kind) if e.get("id") == part_id), None)


def find_real_sequence(kind: str, part_id: str) -> str | None:
    """Returns the real sequence of a part if it is stored in the database
    (sequence_status == "real" and sequence set); otherwise None, so that the
    caller can fall back to the deterministic placeholder sequence."""
    entry = find_part(kind, part_id)
    if not entry:
        return None
    seq = entry.get("sequence")
    if not seq or entry.get("sequence_status") != "real":
        return None
    return seq


STOP_CODONS = ("TAA", "TAG", "TGA")
# Categories whose bare sequence carries neither start nor stop codon: the software adds ATG / a stop codon per slot (constructs.py)
CODING_CATEGORIES = ("shell", "cargo", "marker", "intein", "tp")


def bare_cds(sequence: str) -> str:
    """A coding sequence without start codon (ATG) and without stop codon at the end."""
    sequence = (sequence or "").upper()
    if sequence.startswith("ATG"):
        sequence = sequence[3:]
    if sequence[-3:] in STOP_CODONS:
        sequence = sequence[:-3]
    return sequence


def inserts() -> list[dict]:
    """All Level 0 plasmids (parts/level0_inserts/), one entry per plasmid. The files are stored per part (sequence once, plus the list of
    its `plasmids`); here they are expanded: part fields + plasmid fields, `sequence` = the bare part sequence of this plasmid
    (no start/stop codon, no overhangs, no frame spacer). `id` is the plasmid id (None for a plasmid that is not built)."""
    out = []
    for part in _read_kind("level0_inserts"):
        shared = {k: v for k, v in part.items() if k not in ("plasmids", "sequence", "length_bp", "checks")}
        for plasmid in part.get("plasmids", []):
            sequence = plasmid.get("sequence", part.get("sequence"))
            out.append({**shared, "checks": part.get("checks", {}), **plasmid, "part_file_id": part["id"],
                        "sequence": sequence, "length_bp": len(sequence)})
    return sorted(out, key=lambda e: e["id"] or "~")  # plasmids without an id (not built) come last


def find_inserts(category: str, part: str | None = None, site: str | None = None, slot: int | None = None,
                 **extra) -> list[dict]:
    """Inserts of one category (shell, cargo, linker, marker, intein, tp, ncs), optionally filtered by part id,
    site ("nc_site"/"cargo_site"), Type slot and further fields (variant="c_term", ncs_role="stop", ...)."""
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


def plasmid_status(entry: dict | None) -> str:
    """State of a Level 0 plasmid entry: "stock" (built, glycerol stock), "no_stock" (has an internal id but no stock) or
    "not_built" (no internal id: not built and not in the lab system, listed only for completeness). No entry at all (a part used at a
    slot where no plasmid exists) counts as not built."""
    if not entry or not entry.get("id"):
        return "not_built"
    return "stock" if entry.get("on_stock") else "no_stock"


def find_library_cargo(sequence: str) -> dict | None:
    """The cargo entry of the library whose sense sequence is `sequence` (a toolkit part, not a user input), otherwise None.
    A start codon in front or a stop codon at the end of `sequence` does not matter."""
    return next((e for e in find_inserts("cargo") if e["sequence"] == bare_cds(sequence)), None)
