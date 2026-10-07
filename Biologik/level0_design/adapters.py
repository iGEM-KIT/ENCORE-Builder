"""The overhang adapters of the Type slots (parts/type_overhangs/): insert a part sequence, neighbour context, rotate by 180 degrees for the cargo site."""

from __future__ import annotations

import re

from .genbank_writer import location_span, shift_location
from .parts_db import find_part
from .sequence import reverse_complement


def attach_adapter(adapter, insert_seq: str) -> dict:
    """Attaches the overhang flanks of a Type adapter (parts/type_overhangs/) to a CDS or part sequence:
    the 4-nt placeholder ("Insert", e.g. AAAA) is replaced by the sequence.

    `adapter` is the id ("0.1", "0.1rc", "0.2", ...) or the already loaded entry. The sequence is inserted
    unchanged; the orientation (for the rc adapters of the cargo site) is up to the caller. All features after
    the insert are shifted by the length difference; at the end every overhang and every BbsI site is checked
    against the new sequence, so that a shifted position never passes silently."""
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
    """Which adapter (parts/type_overhangs/) applies to a part in module `module` ("cargo"/"nc") at Type 0.<slot>:
    at the outer slots 0.1/0.5 the cargo site has its own rc adapters, 0.2 to 0.4 apply to both sides."""
    return f"0.{slot}rc" if module == "cargo" and slot in (1, 5) else f"0.{slot}"


def adapter_contexts(adapter_id: str, antisense: bool) -> tuple:
    """Neighbour context of a part sequence on the sense strand of the part: (left variants, right variants). Needed so that the
    codon optimization does not create a BsaI/BbsI site across the seam to the adapter. On the right there are two variants: the
    adapter itself (Level 0) and the overhang with the GC spacer of the next part (Level 1). In the cargo module the part sits
    as a reverse complement in the adapter, so left and right swap sides."""
    entry = find_part("type_overhangs", adapter_id)
    start, end = location_span(entry["insert"]["location"])
    left = entry["sequence"][:start - 1]
    right = entry["sequence"][end:]
    rights = [right, right[:4] + "GC"]
    if antisense:
        return [reverse_complement(r) for r in rights], [reverse_complement(left)]
    return [left], rights


def flip_location(location: str, length: int) -> str:
    """Location after rotating the molecule by 180 degrees (reverse complement of the whole sequence):
    positions are mirrored, the strand flips (complement() on/off), fuzzy markers (<, >) swap."""
    complement = location.startswith("complement(")
    inner = location[len("complement("):-1] if complement else location
    mirror = {"<": ">", ">": "<", "": ""}

    def swap(m):
        lm, a, rm, b = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
        return f"{mirror[rm]}{length - b + 1}..{mirror[lm]}{length - a + 1}"

    inner = re.sub(r"([<>]?)(\d+)\.\.([<>]?)(\d+)", swap, inner)
    return inner if complement else f"complement({inner})"


def rotate_built(built: dict) -> dict:
    """The same construct rotated by 180 degrees: reverse complement of the whole sequence, overhangs/BbsI sites/
    insert at mirrored positions. For the cargo site, so that the cargo reads in its own direction (5' left -> 3' right);
    the construct is physically the same molecule, just read from the other strand."""
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
