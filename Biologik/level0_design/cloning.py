"""BbsI-Klonierung eines Adapter-Konstrukts ins Level-0-Backbone (Plasmid samt GenBank)."""

from __future__ import annotations

from .genbank_writer import format_genbank_record, location_span, make_feature as _feat, shift_location
from .sequence import reverse_complement


def clone_into_level0_backbone(built: dict, label: str, backbone: dict, antisense: bool = False, name: str | None = None) -> dict:
    """BbsI-Klonierung eines Adapter-Konstrukts (attach_adapter) ins Level-0-Backbone.

    BbsI schneidet aus dem Backbone den Stuffer heraus (die Stelle zwischen den Akzeptor-Overhangs
    NLvl0/CLvl0) und aus dem Konstrukt das Fragment vom Level-0-N- bis zum Level-0-C-Overhang — die
    BbsI-Erkennungsstellen des Adapters bleiben im verworfenen Rest zurueck. Die vier-Basen-Enden
    beider Fragmente sind identisch und ligieren: Plasmid = Backbone bis vor NLvl0 + Fragment + Backbone
    ab nach CLvl0. An den Naehten entstehen die BsaI-Stellen fuer Level 1 neu (GGT|CTC und GAGACC).
    Annotationen: alles vom Backbone, was ausserhalb des herausgeschnittenen Bereichs liegt, plus die
    Overhangs und das Insert aus dem Adapter. Features im Stuffer (lacZ-alpha, MCS, BbsI-Stellen, ...)
    sind mit dem Stuffer verschwunden. Die Sequenz ist immer der Top-Strand, 5' links -> 3' rechts;
    `antisense` (Cargo-Modul): das Insert liegt im Backbone-Top-Strand antisense -> CDS-Feature mit complement()."""
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
            # die beiden BsaI-Stellen ragen an der Naht in den Austauschbereich hinein; die Basen werden von
            # Backbone und Fragment gemeinsam neu zusammengesetzt (GGT|CTC bzw. GAG|ACC) — Stelle bleibt erhalten
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
