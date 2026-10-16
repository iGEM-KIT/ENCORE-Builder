"""Static data and constants for the Level 0 design."""

from __future__ import annotations


from .parts_db import find_inserts, load_parts, plasmid_status
from .genbank_writer import format_backbone_record

# Stop codons: these triplets mark the end of a protein coding sequence; STOP_CODONS is a variable
STOP_CODONS = ["TAA", "TAG", "TGA"]

# Definition of the first part of a primer that is needed for assembly.
# It is the same for all primers in Golden Gate assembly and is stored here as a constant.

BSAI_PRIMER_PREFIX = "GGTCTCN"

# BsaI flanks of the cargo module (Level 1), used by the primer calculation. They correspond to the Level 2 overhangs
# of the adapters 0.1rc/0.5rc (parts/type_overhangs/): CCAA on the left, GCAA on the right (= complement of CGTT).
CARGO_L1_FLANK = ["CCAA", "GCAA"]

# Approximate lengths of the individual building blocks in base pairs (bp), not the real biological length.
# When a module is built, the program knows roughly how many base pairs it has and can compute the
# total number of base pairs more easily.
# It is also handy for displaying the plasmid in the user interface.

NOMINAL_BP = {
    "TP": 54,
    "PROMO": 680,
    "NCS": 15,
}

# The part sequences (shells, cargos, linkers, markers, TPs, NCS) come from the sequence database parts/level0_inserts/:
# one entry per Level 0 plasmid with the bare part sequence (without overhangs and frame spacer), the Type slot, the site
# (nc_site / cargo_site, derived from the Level 2 overhangs and the orientation in the plasmid). The lists
# below only supply ids/labels/metadata for the dropdowns; which part really exists at which slot of which site
# is recorded in the database ("slots" in each library).

SITE_KEY = {"nc_site": "nc", "cargo_site": "cargo"}


def _slots(category: str, part: str, **extra) -> dict:
    """{"nc": [slots...], "cargo": [slots...]}: where a Level 0 plasmid exists for this part."""
    out = {"nc": [], "cargo": []}
    for entry in find_inserts(category, part, **extra):
        if entry.get("type_slot") is None:
            continue  # combined spacers (covers_slots) are not offered in the slot dropdowns yet
        key = SITE_KEY[entry["site"]]
        if entry["type_slot"] not in out[key]:
            out[key].append(entry["type_slot"])
    return {key: sorted(value) for key, value in out.items()}


def _status(category: str, part: str, **extra) -> dict:
    """{"nc": {"2": "built", ...}, "cargo": {...}}: state of the Level 0 plasmid of this part per site and slot (see plasmid_status)."""
    out = {"nc": {}, "cargo": {}}
    for entry in find_inserts(category, part, **extra):
        if entry.get("type_slot") is not None:
            out[SITE_KEY[entry["site"]]][str(entry["type_slot"])] = plasmid_status(entry)
    return out


def _length(category: str, part: str):
    """Length of a part as it sits in the ORF: the bare sequence, plus start and stop codon for a shell (always a complete ORF)."""
    entry = next(iter(find_inserts(category, part)), None)
    return len(entry["sequence"]) + (6 if category == "shell" else 0) if entry else None


# Libraries for nanocompartments
# Each predefined nanocompartment has: ID (internal communication); label (shown in the user interface);
# temperature T; diameter dia; targeting peptide tp; protein the nanocompartment shell consists of (shell)

NANOCOMPARTMENTS = [
    {"id": "tmari", "label": "Thermotoga maritima", "T": 1, "dia": "24 nm", "tp": "TP-Tm", "shell": "E-Tm"},
    {"id": "mxan", "label": "Myxococcus xanthus", "T": 3, "dia": "32 nm", "tp": "TP-Mx", "shell": "E-Mx"},
    {"id": "qther", "label": "Quasibacillus thermotolerans", "T": 4, "dia": "42 nm", "tp": "TP-Qt", "shell": "E-Qt"},
    # The human vault is no encapsulin: no triangulation number, barrel of about 41 x 73 nm. Its targeting peptide is the intein INT.
    {"id": "mvp", "label": "Major vault protein (vault)", "T": None, "dia": "41 x 73 nm", "tp": "INT", "shell": "MVP"},
]
for _nc in NANOCOMPARTMENTS:
    _nc["shellBp"] = _length("shell", _nc["shell"]) or 0
    _shell = next(iter(find_inserts("shell", _nc["shell"])), None)
    _nc["status"] = plasmid_status(_shell)


# Cargo templates = the cargo inserts of the database (Type 0.3, cargo site). Adding a new cargo now only means
# creating a JSON file in parts/level0_inserts/, no Python change.

def _load_cargo_presets() -> list[dict]:
    return [
        {"id": entry["part"], "label": entry["part_label"], "seq": entry["sequence"], "notes": entry.get("notes"),
         "status": plasmid_status(entry)}
        for entry in find_inserts("cargo")
        if entry.get("sequence")
    ]


CARGO_PRESETS = _load_cargo_presets()

# Library for linkers with amino acids aa; short description desc; repeat sequence repeat; number of
# repeats n; kind of linker type. Length (bp) and slots come from the database.
_LINKER_META = [
    ("GGS2", "2×(GGS)", "short · very flexible", "GGS", 2),
    ("GSSS2", "2×(GSSS)", "short · flexible", "GSSS", 2),
    ("GSSS3", "3×(GSSS)", "medium · flexible", "GSSS", 3),
    ("GSSS4", "4×(GSSS)", "long · flexible", "GSSS", 4),
]
LINKERS = [
    {"id": pid, "label": label, "aa": (_length("linker", pid) or 0) // 3, "bp": _length("linker", pid) or 0, "desc": desc,
     "repeat": repeat, "n": n, "type": "flexible", "slots": _slots("linker", pid), "status": _status("linker", pid)}
    for pid, label, desc, repeat, n in _LINKER_META
    if _length("linker", pid)
]

# Library for promoters
PROMOTERS = [{"id": "GAL110", "label": "GAL1-10", "desc": "bidirectional, inducible"}]

# Surface markers. They can be put into one of the slots next to the shell
# (Type 1, 2, 4, 5) and therefore sit on the OUTSIDE of the encapsulin, in contrast
# to the cargo, which is packed inside.
_MARKER_META = [
    ("spycatcher", "SpyCatcher", "covalent SpyTag capture (isopeptide bond)"),
    ("spytag", "SpyTag", "13-aa peptide, binds SpyCatcher"),
]
SURFACE_MARKERS = [
    {"id": pid, "label": label, "aa": (_length("marker", pid) or 0) // 3, "bp": _length("marker", pid) or 0, "desc": desc,
     "slots": _slots("marker", pid), "status": _status("marker", pid)}
    for pid, label, desc in _MARKER_META
    if _length("marker", pid)
]

# INT (Type 0.1, cargo site) and the targeting peptides (cargo site only: C-terminal in Type 0.1 with stop codon, N-terminal
# in Type 0.5 with start codon), each with the slots where a Level 0 plasmid exists.
INTEINS = [
    {"id": "int", "label": "INT", "aa": (_length("intein", "int") or 0) // 3, "bp": _length("intein", "int") or 0,
     "desc": "INT", "slots": _slots("intein", "int"), "status": _status("intein", "int")}
] if _length("intein", "int") else []
def _tp_entry(nc: dict) -> dict:
    """Targeting peptide of a nanocompartment. For the vault it is the intein INT (a Level 0 part of the category intein), offered like the other targeting peptides in the cargo module only."""
    if nc["id"] == "mvp":
        slots, status = _slots("intein", "int"), _status("intein", "int")
        return {"id": nc["tp"], "label": f"Targeting peptide {nc['tp']}", "bp": _length("intein", "int") or 0,
                "slots": {"nc": [], "cargo": slots.get("cargo", [])}, "status": {"nc": {}, "cargo": (status or {}).get("cargo", {})}}
    return {"id": nc["tp"], "label": f"Targeting peptide {nc['tp']}", "bp": NOMINAL_BP["TP"], "slots": _slots("tp", nc["tp"]), "status": _status("tp", nc["tp"])}


TARGETING_PEPTIDES = [_tp_entry(nc) for nc in NANOCOMPARTMENTS if nc["tp"]]


def _ncs_slots() -> dict:
    """Where an NCS spacer exists per site and slot: {"nc": {"1": ["plain"], ...}, "cargo": {...}}. There is one NCS sequence
    (no NCS with stop codon: the stop codon is added behind the last coding part), so the only variant is "plain"."""
    out = {"nc": {}, "cargo": {}}
    for entry in find_inserts("ncs"):
        if entry.get("type_slot") is None:
            continue  # combined spacers (covers_slots) are not offered in the slot dropdowns yet
        out[SITE_KEY[entry["site"]]][str(entry["type_slot"])] = ["plain"]
    return out


def _ncs_status() -> dict:
    """State of the NCS plasmids: {"nc": {"1": {"plain": "built"}, ...}, "cargo": {...}}."""
    out = {"nc": {}, "cargo": {}}
    for entry in find_inserts("ncs"):
        if entry.get("type_slot") is not None:
            out[SITE_KEY[entry["site"]]][str(entry["type_slot"])] = {"plain": plasmid_status(entry)}
    return out


def _ncs_combined() -> list:
    """The combined NCS spacers, each one Level 0 part that replaces two neighbouring NCS parts:
    [{"id": "ncs12", "label": "NCS 0.12", "slots": [1, 2], "status": {"nc": "not_built", "cargo": "not_built"}}, ...]."""
    out = {}
    for entry in find_inserts("ncs"):
        covers = entry.get("covers_slots")
        if not covers:
            continue
        key = "".join(str(n) for n in covers)
        item = out.setdefault(key, {"id": f"ncs{key}", "label": f"NCS 0.{key}", "slots": list(covers), "status": {}})
        item["status"][SITE_KEY[entry["site"]]] = plasmid_status(entry)
    return [out[key] for key in sorted(out)]


# Everything the frontend needs for its dropdowns, in ONE place.
# On purpose a function and not a constant, so that it can read from the database
# later without the callers changing.

def _public(entry: dict) -> dict:
    """A parts database entry as the frontend gets it: without its internal bookkeeping fields."""
    return {k: v for k, v in entry.items() if k != "on_stock"}


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
        "ncsStatus": _ncs_status(),
        "ncsCombined": _ncs_combined(),
        # The backbones come from the parts database (Biologik/level0_design/parts/README.md); the Level 0 backbone
        # with its finished GenBank text (copy/download in the frontend, step 4 / Level 0).
        "level0Backbones": [{**_public(b), "genbank": format_backbone_record(b)} for b in parts["level0_backbones"] if b.get("sequence")],
        "level1Backbones": [{**_public(b), "genbank": format_backbone_record(b)} for b in parts["level1_backbones"] if b.get("sequence")],
        "level2Backbones": [{**_public(b), "genbank": format_backbone_record(b)} for b in parts["level2_backbones"] if b.get("sequence")],
    }


# Search functions for the libraries to find an element by its ID.

def find_nanocompartment(identifier: str):
    # next(...) looks for the first matching element and returns it.
    return next((item for item in NANOCOMPARTMENTS if item["id"] == identifier), None)


def find_linker(identifier: str):
    return next((item for item in LINKERS if item["id"] == identifier), None)


def find_promoter(identifier: str):
    return next((item for item in PROMOTERS if item["id"] == identifier), None)


def find_surface_marker(identifier: str):
    return next((item for item in SURFACE_MARKERS if item["id"] == identifier), None)


def find_intein(identifier: str):
    return next((item for item in INTEINS if item["id"] == identifier), None)
