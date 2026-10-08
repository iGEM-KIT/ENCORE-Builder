"""The overhang adapters of the Type slots (parts/type_overhangs/): insert a part sequence, neighbour context, rotate by 180 degrees for the cargo site."""

from __future__ import annotations

import re

from .genbank_writer import location_span, shift_location
from .parts_db import find_part
from .sequence import reverse_complement


def spacer_mode(module: str, slot: int) -> str:
    """Where the 2-nt frame spacer sits relative to the insert, on the top strand of the Level 0 plasmid:
    "before" (nanocompartment site: overhang, spacer, part), "after" (cargo site, Type 0.1 to 0.4: part, spacer, overhang; the
    cargo module is the reverse complement of that layout, so in its reading direction the spacer again follows the overhang) or
    "drop" (cargo Type 0.5: it is the first part in reading direction, no part precedes it, the junction to the promoter
    has no spacer)."""
    if module != "cargo":
        return "before"
    return "drop" if slot == 5 else "after"


def _relocate_spacer(entry: dict, mode: str) -> dict:
    """Copy of the adapter `entry` with the frame spacer behind the insert placeholder ("after": the two blocks swap places,
    everything else stays) or left out entirely ("drop": everything behind shifts by the spacer length)."""
    sp = entry.get("frame_spacer")
    if mode == "before" or not sp:
        return entry
    sp_a, sp_b = location_span(sp["location"])
    ins_a, ins_b = location_span(entry["insert"]["location"])
    if sp_b + 1 != ins_a:
        raise ValueError(f"Adapter {entry['id']}: the frame spacer does not sit directly in front of the insert placeholder.")
    seq, n = entry["sequence"], sp_b - sp_a + 1
    entry = {**entry, "insert": dict(entry["insert"]), "frame_spacer": dict(sp)}
    if mode == "after":
        entry["sequence"] = seq[:sp_a - 1] + seq[ins_a - 1:ins_b] + seq[sp_a - 1:sp_b] + seq[ins_b:]
        new_insert, new_spacer = f"{sp_a}..{sp_a + (ins_b - ins_a)}", f"{sp_a + (ins_b - ins_a) + 1}..{ins_b}"
        relocated = {sp["location"]: new_spacer, entry["insert"]["location"]: new_insert}
        entry["features"] = [{**f, "location": relocated.get(f["location"], f["location"])} for f in entry["features"]]
        entry["insert"]["location"], entry["frame_spacer"]["location"] = new_insert, new_spacer
        return entry
    entry["sequence"] = seq[:sp_a - 1] + seq[ins_a - 1:]

    def moved(item: dict) -> dict:
        a, _ = location_span(item["location"])
        return {**item, "location": shift_location(item["location"], -n) if a > sp_b else item["location"]}

    entry["features"] = [moved(f) for f in entry["features"] if f["location"] != sp["location"]]
    entry["overhangs"] = [moved(o) for o in entry["overhangs"]]
    entry["bbsi_sites"] = [moved(b) for b in entry["bbsi_sites"]]
    entry["insert"]["location"] = shift_location(entry["insert"]["location"], -n)
    entry["frame_spacer"] = None
    entry["length_bp"] = len(entry["sequence"])
    return entry


def attach_adapter(adapter, insert_seq: str, spacer: str = "before") -> dict:
    """Attaches the overhang flanks of a Type adapter (parts/type_overhangs/) to a CDS or part sequence:
    the 4-nt placeholder ("Insert", e.g. AAAA) is replaced by the sequence.

    `spacer` is where the frame spacer goes ("before" the insert as stored, "after" it, or "drop", see `spacer_mode`).
    `adapter` is the id ("0.1", "0.1rc", "0.2", ...) or the already loaded entry. The sequence is inserted
    unchanged; the orientation (for the rc adapters of the cargo site) is up to the caller. All features after
    the insert are shifted by the length difference; at the end every overhang and every BbsI site is checked
    against the new sequence, so that a shifted position never passes silently."""
    entry = adapter if isinstance(adapter, dict) else find_part("type_overhangs", adapter)
    if not entry or not entry.get("sequence"):
        raise ValueError(f"Unknown or empty overhang adapter: {adapter!r}")
    entry = _relocate_spacer(entry, spacer)
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


def adapter_contexts(adapter_id: str, antisense: bool, slot: int | None = None) -> tuple:
    """Neighbour context of a part sequence on the sense strand of the part: (left variants, right variants). Needed so that the
    codon optimization does not create a BsaI/BbsI site across the seam to the adapter. Two variants each: the adapter itself
    (Level 0) and the overhang with the GC spacer of the neighbouring part (Level 1). In the cargo module the part sits as a
    reverse complement in the adapter with its spacer behind it (see `spacer_mode`), so left and right swap sides."""
    entry = find_part("type_overhangs", adapter_id)
    start, end = location_span(entry["insert"]["location"])
    left = entry["sequence"][:start - 1]
    right = entry["sequence"][end:]
    if not antisense:
        return [left], [right, right[:4] + "GC"]
    spacer = entry["frame_spacer"]["sequence"] if entry.get("frame_spacer") else ""
    left = left[:len(left) - len(spacer)] if spacer and left.endswith(spacer) else left   # the spacer moves behind the insert
    lefts = [left] + ([spacer + left[-4:]] if slot is None or slot > 1 else [])
    rights = [right if slot == 5 else spacer + right, right[:4] if slot == 5 else spacer + right[:4]]
    return [reverse_complement(r) for r in rights], [reverse_complement(l) for l in lefts]


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
