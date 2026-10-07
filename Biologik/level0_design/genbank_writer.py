"""Minimal GenBank flat file writer (no external dependency needed,
in line with the rest of the repo; see commec-service/app.py for the same
standard-library-only philosophy). Replaces the former plain FASTA export: FASTA
has no feature table, GenBank does; that was the point: to keep real
annotations (Type assignment, source PLACEHOLDER/PARTS DB/REAL INPUT, and for
Level 2 even the real backbone features such as HIS3/AmpR/origins) in the export
instead of losing them on saving.

A "feature" here is a simple dict: {"type", "location", "qualifiers"}
with qualifiers as a list of (key, value) pairs (order is kept,
value=None means a flag qualifier without a value, e.g. /pseudo)."""

from __future__ import annotations


import re
import textwrap

_LOCUS_NAME_RE = re.compile(r"[^A-Za-z0-9_.-]")


def _safe_locus_name(name: str) -> str:
    # LOCUS names must not contain spaces or special characters; shorten to a length
    # accepted in practice by SnapGene/Geneious/Benchling.
    return _LOCUS_NAME_RE.sub("_", name)[:60] or "sequence"


def _format_qualifier(key: str, value) -> str:
    text = f"/{key}" if value is None else f'/{key}="{value}"'
    # GenBank qualifiers wrap at column 80 (21 indentation + up to 59 characters of content).
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
    """A complete LOCUS...// block. Several records can simply be
    appended (standard multi-record GenBank file, importable by all common
    tools as several sequences)."""
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
# Helper functions for the Level 2 merge (real backbone + new insert);
# see design.py: build_genbank(). They work purely on the numbers in the
# location string, so that complement()/join() wrappers are kept
# without having to parse them fully.
# ---------------------------------------------------------------------------

def make_feature(ftype: str, location: str, label: str, note: str | None = None, extra: list | None = None) -> dict:
    qualifiers = [("label", label)]
    if note:
        qualifiers.append(("note", note))
    qualifiers.extend(extra or [])
    return {"type": ftype, "location": location, "qualifiers": qualifiers}


def location_span(location: str) -> tuple[int, int]:
    """(min, max) of all position numbers in a location; enough to
    decide whether a feature lies before/after/inside a region to be
    replaced, also with complement()/join()/fuzzy '>' markers."""
    numbers = [int(n) for n in re.findall(r"\d+", location)]
    return min(numbers), max(numbers)


def shift_location(location: str, shift: int) -> str:
    return re.sub(r"\d+", lambda m: str(int(m.group(0)) + shift), location)


def format_backbone_record(entry: dict) -> str:
    """GenBank text of an imported backbone entry (parts/level*_backbones/) with its complete
    feature table; the qualifiers are stored there as {name: [values]}, the writer expects a list of
    (name, value); /translation is omitted (it can be derived from the sequence)."""
    features = [
        {"type": f["type"], "location": f["location"],
         "qualifiers": [(k, v) for k, values in f["qualifiers"].items() if k != "translation" for v in values]}
        for f in entry.get("features", [])
    ]
    name = entry["id"].split("-")[0]
    return format_genbank_record(name, entry["sequence"], features, entry.get("circular", True), entry.get("label", ""))


def level0_record_name(label: str, slot: int, module: str, kind: str = "") -> str:
    """Name of a Level 0 record from which Type and site can be read directly: e.g. Level0.2_NCS_Cargo / Level0.2_NCS_NC
    (with `kind="Primers"`: Level0.2_Primers_NCS_Cargo). `module` is "cargo"/"nc" (or "cargo_site"/"nc_site")."""
    site = "Cargo" if module.startswith("cargo") else "NC"
    clean = re.sub(r"[^A-Za-z0-9.-]+", "-", label.replace("×", "x")).strip("-") or "part"
    return "_".join(filter(None, (f"Level0.{slot}", kind, clean, site)))
