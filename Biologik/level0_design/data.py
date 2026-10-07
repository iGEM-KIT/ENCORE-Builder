"""Statische Daten und Konstanten für das Level-0-Design."""

from __future__ import annotations


from .parts_db import find_inserts, load_parts
from .genbank_writer import format_backbone_record

# Stop-Codons: Diese Tripletts markieren das Ende einer Proteinkodierung, STOP_CODONS ist eine Variable
STOP_CODONS = ["TAA", "TAG", "TGA"]

# Definition des Anfangsteils eines Primers, der für Assemblierung benötigt wird. 
# Dieser ist beim Golden Gate Assembly für alle Primer gleich und wird hier als Konstante gespeichert.

BSAI_PRIMER_PREFIX = "GGTCTCN"

# BsaI-Flanken des Cargo-Moduls (Level 1) — von der Primer-Berechnung genutzt. Entsprechen den Level-2-Overhangs
# der Adapter 0.1rc/0.5rc (parts/type_overhangs/): links CCAA, rechts GCAA (= Komplement von CGTT).
CARGO_L1_FLANK = ["CCAA", "GCAA"]

# Näherungswerte für die Länge einzelner Bausteine in Basenpaaren (bp), nicht echte biologische Länge
# Wenn ein Modul gebaut wird, weiß das Programm ungefähr, wie viele Basenpaare es hat, und kann die
# Gesamtzahl der Basenpaare einfacher berechnen.
# Auch für die Anzeige des Plasmids in der Benutzeroberfläche ist es praktisch.

NOMINAL_BP = {
    "TP": 54,
    "PROMO": 680,
    "NCS": 15,
}

# Die Teilsequenzen (Shells, Cargos, Linker, Marker, TPs, NCS) kommen aus der Sequenz-Datenbank parts/level0_inserts/:
# je Level-0-Plasmid ein Eintrag mit der reinen Teilsequenz (ohne Overhangs und Frame-Spacer), dem Type-Slot, der Site
# (nc_site / cargo_site — aus den Level-2-Overhangs bzw. der Orientierung im Plasmid) und dem Lagerstatus. Die Listen
# unten liefern nur noch IDs/Labels/Metadaten fuer die Dropdowns; welches Teil an welchem Slot welcher Site wirklich
# existiert, steht in der Datenbank ("slots" in jeder Bibliothek).

SITE_KEY = {"nc_site": "nc", "cargo_site": "cargo"}


def _slots(category: str, part: str, **extra) -> dict:
    """{"nc": [Slots...], "cargo": [Slots...]} — wo es fuer dieses Teil ein Level-0-Plasmid gibt."""
    out = {"nc": [], "cargo": []}
    for entry in find_inserts(category, part, **extra):
        key = SITE_KEY[entry["site"]]
        if entry["type_slot"] not in out[key]:
            out[key].append(entry["type_slot"])
    return {key: sorted(value) for key, value in out.items()}


def _length(category: str, part: str):
    entry = next(iter(find_inserts(category, part)), None)
    return len(entry["sequence"]) if entry else None


# Bibliotheken für Nanokompartimente
# Jedes vordefinierte Nanokompartment hat: ID (interne Kommunikation); Label (angezeigt in der Benutzeroberfäche);
# Temperatur T; Durchmesser dia; Targeting Peptide tp; Protein, aus dem Nanokompartment Hülle besteht Shell

NANOCOMPARTMENTS = [
    {"id": "tmari", "label": "Thermotoga maritima", "T": 1, "dia": "24 nm", "tp": "TP-Tm", "shell": "E-Tm"},
    {"id": "mxan", "label": "Myxococcus xanthus", "T": 3, "dia": "32 nm", "tp": "TP-Mx", "shell": "E-Mx"},
    {"id": "qther", "label": "Quasibacillus thermotolerans", "T": 4, "dia": "42 nm", "tp": "TP-Qt", "shell": "E-Qt"},
]
for _nc in NANOCOMPARTMENTS:
    _nc["shellBp"] = _length("shell", _nc["shell"]) or 0


# Cargo-Vorlagen = die Cargo-Inserts der Datenbank (Type 0.3, Cargo Site). Ein neues Cargo hinzufuegen heisst nur noch:
# eine JSON-Datei in parts/level0_inserts/ anlegen, kein Python aendern.

def _load_cargo_presets() -> list[dict]:
    return [
        {"id": entry["part"], "label": entry["part_label"], "seq": entry["sequence"], "onStock": entry.get("on_stock"),
         "notes": entry.get("notes")}
        for entry in find_inserts("cargo")
        if entry.get("sequence")
    ]


CARGO_PRESETS = _load_cargo_presets()

# Bibliothek für Linker mit Aminosäuren aa; kurze Beschreibung desc; Wiederholungssequenz repeat; Anzahl der
# Wiederholungen n; Art des Linkers type. Laenge (bp) und Slots kommen aus der Datenbank.
_LINKER_META = [
    ("GGS2", "2×(GGS)", "short · very flexible", "GGS", 2),
    ("GSSS2", "2×(GSSS)", "short · flexible", "GSSS", 2),
    ("GSSS3", "3×(GSSS)", "medium · flexible", "GSSS", 3),
    ("GSSS4", "4×(GSSS)", "long · flexible", "GSSS", 4),
]
LINKERS = [
    {"id": pid, "label": label, "aa": (_length("linker", pid) or 0) // 3, "bp": _length("linker", pid) or 0, "desc": desc,
     "repeat": repeat, "n": n, "type": "flexible", "slots": _slots("linker", pid)}
    for pid, label, desc, repeat, n in _LINKER_META
    if _length("linker", pid)
]

# Bibliothek für Promotoren
PROMOTERS = [{"id": "GAL110", "label": "GAL1-10", "desc": "bidirectional, inducible"}]

# Oberflaechen-Marker. Sie lassen sich in einen der Slots neben der Shell legen
# (Type 1, 2, 4, 5) und sitzen dadurch AUSSEN auf dem Encapsulin — im Gegensatz
# zum Cargo, das innen verpackt wird.
_MARKER_META = [
    ("spycatcher", "SpyCatcher", "covalent SpyTag capture (isopeptide bond)"),
    ("spytag", "SpyTag", "13-aa peptide, binds SpyCatcher"),
]
SURFACE_MARKERS = [
    {"id": pid, "label": label, "aa": (_length("marker", pid) or 0) // 3, "bp": _length("marker", pid) or 0, "desc": desc,
     "slots": _slots("marker", pid)}
    for pid, label, desc in _MARKER_META
    if _length("marker", pid)
]

# INT (Type 0.1, Cargo Site) und die Targeting-Peptide (nur Cargo Site: C-terminal in Type 0.1 mit Stopcodon, N-terminal
# in Type 0.5 mit Startcodon) — jeweils mit den Slots, an denen es ein Level-0-Plasmid gibt.
INTEINS = [
    {"id": "int", "label": "INT", "aa": (_length("intein", "int") or 0) // 3, "bp": _length("intein", "int") or 0,
     "desc": "INT", "slots": _slots("intein", "int")}
] if _length("intein", "int") else []
TARGETING_PEPTIDES = [
    {"id": nc["tp"], "label": f"Targeting peptide {nc['tp']}", "slots": _slots("tp", nc["tp"])} for nc in NANOCOMPARTMENTS
]


def _ncs_slots() -> dict:
    """Welche NCS-Varianten ("plain" / "stop") es je Site und Slot gibt: {"nc": {"1": ["plain"], ...}, "cargo": {...}}."""
    out = {"nc": {}, "cargo": {}}
    for entry in find_inserts("ncs"):
        roles = out[SITE_KEY[entry["site"]]].setdefault(str(entry["type_slot"]), [])
        if entry.get("ncs_role") not in roles:
            roles.append(entry.get("ncs_role"))
    return out


# Alles, was das Frontend für seine Dropdowns braucht — an EINER Stelle.
# Bewusst eine Funktion und keine Konstante, damit sie später aus der Datenbank
# lesen kann, ohne dass sich die Aufrufer ändern (siehe PROJECT_TODO.txt, 5).

def get_libraries() -> dict:
    parts = load_parts()
    return {
        "nanocompartments": NANOCOMPARTMENTS,
        "cargoPresets": CARGO_PRESETS,
        "linkers": LINKERS,
        "promoters": PROMOTERS,
        "surfaceMarkers": SURFACE_MARKERS,
        "inteins": INTEINS,
        "targetingPeptides": TARGETING_PEPTIDES,
        "ncs": _ncs_slots(),
        # Die Backbones kommen aus der Parts-Datenbank (Biologik/level0_design/parts/README.md); das Level-0-Backbone
        # samt fertigem GenBank-Text (Copy/Download im Frontend, Step 4 / Level 0).
        "level0Backbones": [{**b, "genbank": format_backbone_record(b)} for b in parts["level0_backbones"] if b.get("sequence")],
        "level1Backbones": [{**b, "genbank": format_backbone_record(b)} for b in parts["level1_backbones"] if b.get("sequence")],
        "level2Backbones": [{**b, "genbank": format_backbone_record(b)} for b in parts["level2_backbones"] if b.get("sequence")],
    }


# Suchfunktionen für die Bibliotheken, um ein Element anhand seiner ID zu finden.

def find_nanocompartment(identifier: str):
    # next(...) sucht das erste passende Element und gibt es zurück.
    return next((item for item in NANOCOMPARTMENTS if item["id"] == identifier), None)


def find_linker(identifier: str):
    return next((item for item in LINKERS if item["id"] == identifier), None)


def find_promoter(identifier: str):
    return next((item for item in PROMOTERS if item["id"] == identifier), None)


def find_surface_marker(identifier: str):
    return next((item for item in SURFACE_MARKERS if item["id"] == identifier), None)


def find_intein(identifier: str):
    return next((item for item in INTEINS if item["id"] == identifier), None)
