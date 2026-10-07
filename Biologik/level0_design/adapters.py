"""Die Overhang-Adapter der Type-Slots (parts/type_overhangs/): Teilsequenz einsetzen, Nachbarkontext, Drehen um 180 Grad fuer die Cargo Site."""

from __future__ import annotations

import re

from .genbank_writer import location_span, shift_location
from .parts_db import find_part
from .sequence import reverse_complement


def attach_adapter(adapter, insert_seq: str) -> dict:
    """Haengt die Overhang-Flanken eines Type-Adapters (parts/type_overhangs/) an eine CDS bzw.
    Teilsequenz: der 4-nt-Platzhalter ("Insert", z.B. AAAA) wird durch die Sequenz ersetzt.

    `adapter` ist die id ("0.1", "0.1rc", "0.2", ...) oder der bereits geladene Eintrag. Die Sequenz
    wird unveraendert eingesetzt — die Orientierung (bei den rc-Adaptern der Cargo Site) liegt beim
    Aufrufer. Alle Features hinter dem Insert werden um die Laengendifferenz verschoben; am Ende wird
    jeder Overhang und jede BbsI-Stelle gegen die neue Sequenz geprueft, damit eine verrutschte
    Position nie still durchgeht."""
    entry = adapter if isinstance(adapter, dict) else find_part("type_overhangs", adapter)
    if not entry or not entry.get("sequence"):
        raise ValueError(f"Unknown or empty overhang adapter: {adapter!r}")
    adapter_id, seq = entry["id"], entry["sequence"]

    cds = (insert_seq or "").upper()
    if not cds or set(cds) - set("ACGT"):
        raise ValueError("The insert sequence must consist of A/C/G/T and must not be empty.")

    start, end = location_span(entry["insert"]["location"])
    placeholder = entry["insert"]["placeholder_sequence"]
    if seq[start - 1:end] != placeholder:
        raise ValueError(f"Adapter {adapter_id}: the placeholder {placeholder} is not at {start}..{end}.")

    shift = len(cds) - (end - start + 1)
    new_seq = seq[:start - 1] + cds + seq[end:]

    def moved(location: str) -> str:
        a, b = location_span(location)
        if b < start:
            return location
        if a > end:
            return shift_location(location, shift)
        raise ValueError(f"Adapter {adapter_id}: feature {location} overlaps the insert placeholder.")

    insert_location = f"{start}..{end + shift}"
    features = []
    for f in entry["features"]:
        if f["location"] == entry["insert"]["location"]:
            features.append({**f, "location": insert_location})
        else:
            features.append({**f, "location": moved(f["location"])})
    overhangs = [{**o, "location": moved(o["location"])} for o in entry["overhangs"]]
    bbsi_sites = [{**b, "location": moved(b["location"])} for b in entry["bbsi_sites"]]

    for item in overhangs + bbsi_sites:
        a, b = location_span(item["location"])
        if new_seq[a - 1:b] != item["sequence_top_strand"]:
            raise ValueError(f"Adapter {adapter_id}: {item['location']} no longer matches after the insert was placed.")

    return {
        "adapter": adapter_id,
        "usedForModules": entry["used_for_modules"],
        "sequence": new_seq,
        "length": len(new_seq),
        "insert": {"location": insert_location, "sequence": cds},
        "overhangs": overhangs,
        "bbsiSites": bbsi_sites,
        "spacers": [dict(entry["frame_spacer"])] if entry.get("frame_spacer") else [],
        "features": features,
    }


def adapter_id_for(module: str, slot: int) -> str:
    """Welcher Adapter (parts/type_overhangs/) fuer ein Teil in Modul `module` ("cargo"/"nc") an Type 0.<slot>
    gilt: an den Aussenslots 0.1/0.5 haben die Cargo Site eigene rc-Adapter, 0.2-0.4 gelten fuer beide Seiten."""
    return f"0.{slot}rc" if module == "cargo" and slot in (1, 5) else f"0.{slot}"


def adapter_contexts(adapter_id: str, antisense: bool) -> tuple:
    """Nachbarkontext einer Teilsequenz im Sense-Strang des Teils: (Links-Varianten, Rechts-Varianten). Gebraucht, damit die
    Codon-Optimierung keine BsaI/BbsI-Stelle ueber die Naht zum Adapter erzeugt. Rechts gibt es zwei Varianten: der Adapter selbst
    (Level 0) und der Overhang mit dem GC-Spacer des naechsten Teils (Level 1). Im Cargo-Modul liegt das Teil als Reverse
    Complement im Adapter, links und rechts tauschen dann die Seiten."""
    entry = find_part("type_overhangs", adapter_id)
    start, end = location_span(entry["insert"]["location"])
    left = entry["sequence"][:start - 1]
    right = entry["sequence"][end:]
    rights = [right, right[:4] + "GC"]
    if antisense:
        return [reverse_complement(r) for r in rights], [reverse_complement(left)]
    return [left], rights


def flip_location(location: str, length: int) -> str:
    """Location nach einer Drehung des Molekuels um 180 Grad (Reverse Complement der ganzen Sequenz):
    Positionen werden gespiegelt, der Strang kippt (complement() an/aus), fuzzy-Markierungen (<, >) tauschen."""
    complement = location.startswith("complement(")
    inner = location[len("complement("):-1] if complement else location
    mirror = {"<": ">", ">": "<", "": ""}

    def swap(m):
        lm, a, rm, b = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
        return f"{mirror[rm]}{length - b + 1}..{mirror[lm]}{length - a + 1}"

    inner = re.sub(r"([<>]?)(\d+)\.\.([<>]?)(\d+)", swap, inner)
    return inner if complement else f"complement({inner})"


def rotate_built(built: dict) -> dict:
    """Dasselbe Konstrukt, um 180 Grad gedreht: Reverse Complement der gesamten Sequenz, Overhangs/BbsI-Stellen/
    Insert an gespiegelten Positionen. Fuer die Cargo Site, damit das Cargo (5' links -> 3' rechts) in seiner
    eigenen Leserichtung steht — das Konstrukt ist physisch dasselbe Molekuel, nur vom anderen Strang gelesen."""
    length = built["length"]
    seq = reverse_complement(built["sequence"])

    def flipped(item: dict) -> dict:
        loc = flip_location(item["location"], length)
        a, b = location_span(loc)
        top = seq[a - 1:b]
        out = {**item, "location": loc, "sequence_top_strand": top}
        if "strand" in item:
            out["strand"] = "-" if loc.startswith("complement(") else "+"
        if "sequence_own_strand_5to3" in item:
            out["sequence_own_strand_5to3"] = reverse_complement(top) if loc.startswith("complement(") else top
        return out

    insert_loc = flip_location(built["insert"]["location"], length)
    return {
        **built,
        "sequence": seq,
        "insert": {"location": insert_loc.replace("complement(", "").rstrip(")") if insert_loc.startswith("complement(") else insert_loc,
                   "sequence": reverse_complement(built["insert"]["sequence"])},
        "overhangs": [flipped(o) for o in built["overhangs"]],
        "bbsiSites": [flipped(b) for b in built["bbsiSites"]],
        "spacers": [{**sp, "location": flip_location(sp["location"], length)} for sp in built.get("spacers", [])],
        "stops": [{**st, "location": flip_location(st["location"], length)} for st in built.get("stops", [])],
    }
