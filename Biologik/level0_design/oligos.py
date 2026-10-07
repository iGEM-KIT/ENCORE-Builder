"""Oligo pairs for parts that are too short for PCR: anneal them and ligate directly into the Level 0 backbone."""

from __future__ import annotations

from .genbank_writer import (format_genbank_record, level0_record_name, location_span, make_feature as _feat,
                             shift_location)
from .sequence import reverse_complement


def design_level0_oligos(built: dict, label: str, slot: int, module: str) -> dict:
    """Two complementary oligos for a part that is too short for PCR primers: annealing directly gives the
    BbsI-cut fragment (overhangs 0N/0C as 5' overhangs), which ligates into the Level 0 backbone without further digest.
    Top: from the 0N overhang to just before the 0C overhang; bottom: reverse complement of everything after 0N up to and including 0C."""
    roles = {o["role"]: o for o in built["overhangs"]}
    n0, n1 = location_span(roles["level0_N"]["location"])
    c0, c1 = location_span(roles["level0_C"]["location"])
    seq = built["sequence"]
    top, bottom = seq[n0 - 1:c0 - 1], reverse_complement(seq[n1:c1])
    base = level0_record_name(label, slot, module, "Oligo")
    stop = None
    if built.get("stops"):
        a0, b0 = (v - 1 for v in location_span(built["stops"][0]["location"]))  # 0-based, top strand of the plasmid
        t = (a0 - (n0 - 1), b0 - (n0 - 1))
        u = (c1 - 1 - b0, c1 - 1 - a0)
        stop = {"top": list(t) if 0 <= t[0] and t[1] < len(top) else None,
                "bottom": list(u) if a0 >= n1 and 0 <= u[0] and u[1] < len(bottom) else None}
    # GenBank record of the annealed fragment (top strand of the Level 0 plasmid, 0N overhang to 0C overhang) with both oligos
    shift = n0 - 1
    rel = lambda loc: shift_location(loc, -shift)
    feats = [_feat("primer_bind", f"1..{len(top)}", f"{base}_F", f"oligo {base}_F 5'-{top}-3'"),
             _feat("primer_bind", f"complement({n1 - n0 + 2}..{c1 - n0 + 1})", f"{base}_R", f"oligo {base}_R 5'-{bottom}-3'")]
    feats += [_feat("overhang", rel(o["location"]), o["label"], f"{o['role']} · top strand {o['sequence_top_strand']}")
              for o in built["overhangs"]]
    feats += [_feat("misc_feature", rel(sp["location"]), "Frame spacer", sp["note"]) for sp in built.get("spacers", [])]
    feats += [_feat("misc_feature", rel(st["location"]), "Stop codon", st["note"]) for st in built.get("stops", [])]
    antisense = module.startswith("cargo")
    insert_loc = rel(built["insert"]["location"])
    feats.append(_feat("CDS", f"complement({insert_loc})" if antisense else insert_loc, label,
                       "part" + (", antisense: the ORF reads on the complement strand" if antisense else "")))
    feats.sort(key=lambda f: location_span(f["location"])[0])
    fragment = seq[n0 - 1:c1]
    definition = (f"Annealed oligo pair for {label} (Type 0.{slot}, {'cargo' if antisense else 'nanocompartment'} site): "
                  f"5' overhangs {seq[n0 - 1:n1]} / {reverse_complement(seq[c0 - 1:c1])} fit the Level 0 backbone, no digest needed. "
                  "Sequence = top strand of the Level 0 plasmid, 5'->3' left to right.")
    return {
        "genbank": format_genbank_record(level0_record_name(label, slot, module, "Oligos"), fragment, feats, False, definition),
        "stop": stop,
        "possible": True,
        "top": {"name": f"{base}_F", "sequence": top, "length": len(top)},
        "bottom": {"name": f"{base}_R", "sequence": bottom, "length": len(bottom)},
        "overhangs": {"left": seq[n0 - 1:n1], "right": reverse_complement(seq[c0 - 1:c1])},
        "annealedLength": len(seq[n0 - 1:c1]),
    }
