"""BbsI cloning of an adapter construct into the Level 0 backbone (plasmid including GenBank)."""

from __future__ import annotations

from .genbank_writer import format_genbank_record, location_span, make_feature as _feat, shift_location
from .sequence import reverse_complement


def clone_into_level0_backbone(built: dict, label: str, backbone: dict, antisense: bool = False, name: str | None = None) -> dict:
    """BbsI cloning of an adapter construct (attach_adapter) into the Level 0 backbone.

    BbsI cuts the stuffer out of the backbone (the region between the acceptor overhangs NLvl0/CLvl0) and
    from the construct the fragment from the Level 0 N overhang to the Level 0 C overhang; the BbsI recognition
    sites of the adapter stay behind in the discarded rest. The four-base ends of both fragments are identical
    and ligate: plasmid = backbone up to NLvl0 + fragment + backbone after CLvl0. At the seams the BsaI sites for
    Level 1 form anew (GGT|CTC and GAGACC).
    Annotations: everything from the backbone that lies outside the excised region, plus the overhangs and the
    insert from the adapter. Features in the stuffer (lacZ-alpha, MCS, BbsI sites, ...) disappeared with the
    stuffer. The sequence is always the top strand, 5' left -> 3' right;
    `antisense` (cargo module): the insert lies antisense in the backbone top strand -> CDS feature with complement()."""
    seq = backbone["sequence"]
    oh5 = backbone["receiver_overhangs"]["5_prime"]
    oh3 = backbone["receiver_overhangs"]["3_prime"]
    bb_n0, bb_n1 = location_span(oh5["location"])
    bb_c0, bb_c1 = location_span(oh3["location"])
    roles = {o["role"]: o for o in built["overhangs"]}
    ad_n0, _ = location_span(roles["level0_N"]["location"])
    _, ad_c1 = location_span(roles["level0_C"]["location"])
    if seq[bb_n0 - 1:bb_n1] != roles["level0_N"]["sequence_top_strand"] or \
            seq[bb_c0 - 1:bb_c1] != roles["level0_C"]["sequence_top_strand"]:
        raise ValueError(f"Adapter {built['adapter']}: the Level 0 overhangs do not match backbone {backbone['id']}.")

    fragment = built["sequence"][ad_n0 - 1:ad_c1]
    new_seq = seq[:bb_n0 - 1] + fragment + seq[bb_c1:]
    tail_shift = len(fragment) - (bb_c1 - bb_n0 + 1)
    adapter_to_plasmid = bb_n0 - ad_n0
    insert_start, insert_end = bb_n0, bb_n0 + len(fragment) - 1

    features = []
    for f in backbone.get("features", []):
        lo, hi = location_span(f["location"])
        lab = (f["qualifiers"].get("label") or [""])[0]
        loc = None
        if f["type"] == "source":
            loc = f"1..{len(new_seq)}"
        elif hi < bb_n0:
            loc = f["location"]
        elif lo > bb_c1:
            loc = shift_location(f["location"], tail_shift)
        elif lab == "BsaI rec site":
            # the two BsaI sites reach into the replaced region at the seam; the bases are reassembled by
            # backbone and fragment together (GGT|CTC and GAG|ACC), so the site is kept
            loc = f["location"] if lo < bb_n0 else shift_location(f["location"], tail_shift)
            a, b = location_span(loc)
            site = new_seq[a - 1:b]
            if (reverse_complement(site) if loc.startswith("complement(") else site) != "GGTCTC":
                raise ValueError(f"BsaI site {loc} is not intact after cloning.")
        if loc is not None:
            quals = [(k, v) for k, vals in f["qualifiers"].items() if k != "translation" for v in vals]
            features.append({"type": f["type"], "location": loc, "qualifiers": quals})

    for o in built["overhangs"]:
        features.append(_feat("overhang", shift_location(o["location"], adapter_to_plasmid), o["label"],
                              f"{o['role']} · top strand {o['sequence_top_strand']}"))
    for sp in built.get("spacers", []):
        features.append(_feat("misc_feature", shift_location(sp["location"], adapter_to_plasmid), "Frame spacer", sp["note"]))
    for st in built.get("stops", []):
        features.append(_feat("misc_feature", shift_location(st["location"], adapter_to_plasmid), "Stop codon", st["note"]))
    insert_loc = shift_location(built["insert"]["location"], adapter_to_plasmid)
    features.append(_feat("CDS", f"complement({insert_loc})" if antisense else insert_loc, label,
                          f"Insert cloned via BbsI into {backbone['id']} · adapter {built['adapter']} · "
                          + ("antisense: the ORF reads on the complement strand" if antisense else "sense strand")))
    features.sort(key=lambda f: (location_span(f["location"])[0], location_span(f["location"])[1]))

    for f in features:
        a, b = location_span(f["location"])
        if a < 1 or b > len(new_seq):
            raise ValueError(f"Feature {f['location']} lies outside the plasmid.")

    name = name or f"{backbone['id'].split('-')[0]}-{label.replace(' ', '-')}"
    definition = (f"{backbone['label']} with {label} cloned in via BbsI (adapter {built['adapter']}): the "
                  f"{bb_c1 - bb_n0 + 1} bp stuffer between {oh5['label']} and {oh3['label']} is replaced by "
                  f"{len(fragment)} bp; the adapter's BbsI sites are cut away, BsaI sites for Level 1 remain.")
    return {
        "name": name, "sequence": new_seq, "length": len(new_seq),
        "insertStart": insert_start, "insertEnd": insert_end,
        "genbank": format_genbank_record(name, new_seq, features, True, definition),
    }
