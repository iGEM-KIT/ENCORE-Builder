"""Minimaler GenBank-Flatfile-Schreiber (keine externe Abhaengigkeit noetig,
passend zum Rest des Repos; siehe commec-service/app.py fuer dieselbe
Stdlib-only-Philosophie). Ersetzt den bisherigen reinen FASTA-Export: FASTA
kennt keine Feature-Tabelle, GenBank schon; genau das war der Punkt, echte
Annotationen (Type-Zuordnung, Quelle PLACEHOLDER/PARTS DB/REAL INPUT, bei
Level 2 sogar die echten Backbone-Features wie HIS3/AmpR/Origins) im Export
zu erhalten statt sie beim Speichern zu verlieren.

Ein "Feature" ist hier ein einfaches dict: {"type", "location", "qualifiers"}
mit qualifiers als Liste von (key, value)-Paaren (Reihenfolge bleibt erhalten,
value=None bedeutet ein Flag-Qualifier ohne Wert, z.B. /pseudo)."""

from __future__ import annotations


import re
import textwrap

_LOCUS_NAME_RE = re.compile(r"[^A-Za-z0-9_.-]")


def _safe_locus_name(name: str) -> str:
    # LOCUS-Namen duerfen keine Leerzeichen/Sonderzeichen enthalten; auf eine
    # in der Praxis von SnapGene/Geneious/Benchling akzeptierte Laenge kuerzen.
    return _LOCUS_NAME_RE.sub("_", name)[:60] or "sequence"


def _format_qualifier(key: str, value) -> str:
    text = f"/{key}" if value is None else f'/{key}="{value}"'
    # GenBank qualifiers wrap at Spalte 80 (21 Einrueckung + bis zu 59 Zeichen Inhalt).
    wrapped = textwrap.wrap(text, width=58, break_long_words=True, break_on_hyphens=False) or [text]
    return "\n".join(" " * 21 + line for line in wrapped)


def _format_feature(feature: dict) -> str:
    ftype = feature["type"]
    location = feature["location"]
    head = f"     {ftype:<16}{location}"
    lines = [head]
    for key, value in feature.get("qualifiers", []):
        lines.append(_format_qualifier(key, value))
    return "\n".join(lines)


def _format_origin(sequence: str) -> str:
    seq = sequence.lower()
    lines = []
    for offset in range(0, len(seq), 60):
        chunk = seq[offset:offset + 60]
        groups = [chunk[i:i + 10] for i in range(0, len(chunk), 10)]
        lines.append(f"{offset + 1:>9} " + " ".join(groups))
    return "\n".join(lines)


def format_genbank_record(name: str, sequence: str, features: list[dict] | None = None,
                           circular: bool = False, definition: str = "") -> str:
    """Ein vollstaendiger LOCUS...// -Block. Mehrere Records lassen sich einfach
    aneinanderhaengen (Standard-GenBank-Multi-Record-Datei, von allen gaengigen
    Tools als mehrere Sequenzen importierbar)."""
    topology = "circular" if circular else "linear"
    lines = [f"LOCUS       {_safe_locus_name(name):<28} {len(sequence)} bp    DNA     {topology}   SYN"]
    if definition:
        lines.append(f"DEFINITION  {definition}")
    lines.append("FEATURES             Location/Qualifiers")
    for feature in (features or []):
        lines.append(_format_feature(feature))
    lines.append("ORIGIN")
    lines.append(_format_origin(sequence))
    lines.append("//")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Hilfsfunktionen fuer den Level-2-Merge (echtes Backbone + neues Insert) —
# siehe design.py: build_genbank(). Arbeiten rein ueber die Zahlen in der
# Location-Zeichenkette, damit complement()/join()-Wrapper erhalten bleiben,
# ohne sie voll parsen zu muessen.
# ---------------------------------------------------------------------------

def make_feature(ftype: str, location: str, label: str, note: str | None = None, extra: list | None = None) -> dict:
    qualifiers = [("label", label)]
    if note:
        qualifiers.append(("note", note))
    qualifiers.extend(extra or [])
    return {"type": ftype, "location": location, "qualifiers": qualifiers}


def location_span(location: str) -> tuple[int, int]:
    """(min, max) aller Positionszahlen in einer Location — reicht, um zu
    entscheiden, ob ein Feature vor/nach/innerhalb eines auszutauschenden
    Bereichs liegt, auch bei complement()/join()/fuzzy '>' Markierungen."""
    numbers = [int(n) for n in re.findall(r"\d+", location)]
    return min(numbers), max(numbers)


def shift_location(location: str, shift: int) -> str:
    return re.sub(r"\d+", lambda m: str(int(m.group(0)) + shift), location)


def format_backbone_record(entry: dict) -> str:
    """GenBank-Text eines importierten Backbone-Eintrags (parts/level*_backbones/) mit seiner kompletten
    Feature-Tabelle — die Qualifier liegen dort als {name: [werte]}, der Writer erwartet eine Liste aus
    (name, wert); /translation wird weggelassen (laesst sich aus der Sequenz ableiten)."""
    features = [
        {"type": f["type"], "location": f["location"],
         "qualifiers": [(k, v) for k, values in f["qualifiers"].items() if k != "translation" for v in values]}
        for f in entry.get("features", [])
    ]
    name = entry["id"].split("-")[0]
    return format_genbank_record(name, entry["sequence"], features, entry.get("circular", True), entry.get("label", ""))


def level0_record_name(label: str, slot: int, module: str, kind: str = "") -> str:
    """Name eines Level-0-Records, an dem man Type und Site direkt erkennt: z.B. Level0.2_NCS_Cargo / Level0.2_NCS_NC
    (mit `kind="Primers"`: Level0.2_Primers_NCS_Cargo). `module` ist "cargo"/"nc" (oder "cargo_site"/"nc_site")."""
    site = "Cargo" if module.startswith("cargo") else "NC"
    clean = re.sub(r"[^A-Za-z0-9.-]+", "-", label.replace("×", "x")).strip("-") or "part"
    return "_".join(filter(None, (f"Level0.{slot}", kind, clean, site)))
