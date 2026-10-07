"""Level 1 and Level 2 assembly by Golden Gate.

Level 0 -> 1 (BsaI): BsaI cuts out of every Level 0 plasmid the fragment from the Level 1 N overhang to the Level 1 C
overhang (= part + Level 1 overhangs, for Type 0.1/0.5 additionally the Level 2 overhangs). The five fragments
of a module ligate through their shared overhangs (ACAT | TATG | TTCT | ATCC | TGGC | TTGT) and end up
between the acceptor overhangs NLvl1/CLvl1 of the Level 1 backbone (pAGM1311).

Level 1 -> 2 (BbsI): BbsI cuts out of the three Level 1 plasmids (cargo module, promoter, NC module) the piece
between the Level 2 overhangs (CCAA ... CGTT | CGTT ... TGAT | TGAT ... AATG) and ligates it between BbLvl2N/
BbLvl2C of the Level 2 backbone (pESC-HIS).

All sequences are the top strand, 5' left -> 3' right. The cargo module lies antisense on it (every part as a
reverse complement), so the matching CDS features carry complement()."""

from __future__ import annotations


from .genbank_writer import format_genbank_record, location_span, make_feature, shift_location
from .parts_db import find_part
from .sequence import reverse_complement

SITES = {"BsaI": ("GGTCTC", "GAGACC"), "BbsI": ("GAAGAC", "GTCTTC")}


def _loc(start: int, end: int, antisense: bool = False) -> str:
    span = f"{start}..{end}"
    return f"complement({span})" if antisense else span


def level1_fragment(built: dict) -> dict:
    """The BsaI fragment of a Level 0 construct (`attach_adapter` result in plasmid orientation): from the
    Level 1 N overhang up to and including the Level 1 C overhang. Coordinates relative to the fragment (1-based)."""
    roles = {o["role"]: o for o in built["overhangs"]}
    n0, _ = location_span(roles["level1_N"]["location"])
    _, c1 = location_span(roles["level1_C"]["location"])
    seq = built["sequence"][n0 - 1:c1]
    overhangs = []
    for o in built["overhangs"]:
        if o["role"] in ("level1_N", "level1_C", "level2_N", "level2_C"):
            a, b = location_span(o["location"])
            overhangs.append({"start": a - n0 + 1, "end": b - n0 + 1, "label": o["label"], "role": o["role"]})
    ia, ib = location_span(built["insert"]["location"])
    spacers = [(location_span(sp["location"])[0] - n0 + 1, location_span(sp["location"])[1] - n0 + 1,
                sp["note"]) for sp in built.get("spacers", [])]
    return {"sequence": seq, "insert": (ia - n0 + 1, ib - n0 + 1), "overhangs": overhangs, "spacers": spacers}


def _site_hits(seq: str) -> list:
    return [(enzyme, site) for enzyme, pair in SITES.items() for site in pair if site in seq]


def _merge_overhangs(items: list) -> list:
    """Merge overhang features at the same position (seam of two fragments) into one, labels joined with ' / '."""
    merged = {}
    for it in items:
        key = (it["start"], it["end"])
        if key in merged:
            if it["label"] not in merged[key]["label"].split(" / "):
                merged[key]["label"] += f" / {it['label']}"
        else:
            merged[key] = dict(it)
    return sorted(merged.values(), key=lambda x: x["start"])


def _overhang_feature(it: dict, seq: str) -> dict:
    return make_feature("overhang", _loc(it["start"], it["end"]), it["label"],
                        f"{it['role']} · top strand {seq[it['start'] - 1:it['end']]}")


def _spacer_feature(sp: dict) -> dict:
    return make_feature("misc_feature", _loc(sp["start"], sp["end"]), "Frame spacer", sp["note"])


def _pack(label: str, what: str, site: str, strand: str, seq: str, parts: list, overhangs: list, notes: list,
          sites: list, name: str, spacers: list | None = None) -> dict:
    """Common shape of a Level 1 insert (also for the promoter)."""
    feats = [_overhang_feature(o, seq) for o in overhangs] + [_spacer_feature(sp) for sp in (spacers or [])]
    for p in parts:
        feats.append(make_feature("CDS" if p["kind"] != "promoter" else "promoter",
                                  _loc(p["start"], p["end"], p["strand"] == "antisense"), p["label"], p["note"]))
    feats.sort(key=lambda f: location_span(f["location"])[0])
    return {
        "spacers": spacers or [],
        "label": label, "what": what, "site": site, "strand": strand, "name": name,
        "sequence": seq, "length": len(seq), "parts": parts,
        "overhangs": [{"label": o["label"], "start": o["start"], "end": o["end"], "role": o["role"],
                       "sequence": seq[o["start"] - 1:o["end"]]} for o in overhangs],
        "level2Overhangs": {"n": seq[4:8], "c": seq[-8:-4]},
        "internalSites": sites, "notes": notes, "_features": feats,
    }


def assemble_level1_module(fragments: list, label: str, site: str, antisense: bool, name: str) -> dict:
    """Five Level 0 fragments (Type 0.1 ... 0.5) into one Level 1 insert. `fragments`: entries with
    "fragment" (level1_fragment), "label", "type", "isReal", "isUser", "what", "insertSequence"."""
    seq, parts, overhangs, sites, placeholders, spacers = "", [], [], [], [], []
    for k, fr in enumerate(fragments):
        f = fr["fragment"]
        if k == 0:
            base = 0
            seq = f["sequence"]
        else:
            if seq[-4:] != f["sequence"][:4]:
                raise ValueError(f"{fr['type']}: overhang {f['sequence'][:4]} does not match the predecessor ({seq[-4:]}).")
            base = len(seq) - 4
            seq += f["sequence"][4:]
        ia, ib = f["insert"]
        parts.append({"label": fr["label"], "type": fr["type"], "start": base + ia, "end": base + ib,
                      "strand": "antisense" if antisense else "sense", "kind": "part", "isReal": fr["isReal"],
                      "isUser": fr["isUser"], "what": fr["what"],
                      "note": f"{fr['type']} · {fr['what']} · Level 1 module ({site.replace('_', ' ')})"})
        for o in f["overhangs"]:
            overhangs.append({**o, "start": base + o["start"], "end": base + o["end"]})
        for a, b, note in f["spacers"]:
            spacers.append({"start": base + a, "end": base + b, "note": note})
        if fr["isReal"]:
            for enzyme, site_seq in _site_hits(fr["insertSequence"]):
                sites.append(f"{enzyme} site ({site_seq}) in {fr['type']} · {fr['label']}")
        else:
            placeholders.append(f"{fr['type']} · {fr['label']}")
    overhangs = _merge_overhangs(overhangs)
    notes = [f"PLACEHOLDER sequence (not in the parts database yet): {', '.join(placeholders)}"] if placeholders else []
    return _pack(label, f"Level 1 {'cargo' if site == 'cargo_site' else 'nanocompartment'} module",
                 site, "antisense" if antisense else "sense", seq, parts, overhangs, notes, sites, name, spacers)


def level2_overhang(adapter_id: str, role: str) -> str:
    """Top strand bases of the Level 2 overhang of an adapter (e.g. ("0.5rc", "level2_C") -> CGTT)."""
    entry = find_part("type_overhangs", adapter_id)
    for o in entry["overhangs"]:
        if o["role"] == role:
            return o["sequence_top_strand"]
    raise ValueError(f"Adapter {adapter_id} hat keinen {role}-Overhang.")


def assemble_level1_promoter(label: str, promoter_seq: str, is_real: bool, name: str, backbone: dict) -> dict:
    """Promoter insert for Level 1: NLvl1 + Level 2 N overhang (= C overhang of the cargo module) + promoter +
    Level 2 C overhang (= N overhang of the NC module) + CLvl1."""
    n1 = backbone["sequence"][location_span(backbone["receiver_overhangs"]["5_prime"]["location"])[0] - 1:
                              location_span(backbone["receiver_overhangs"]["5_prime"]["location"])[1]]
    c1 = backbone["sequence"][location_span(backbone["receiver_overhangs"]["3_prime"]["location"])[0] - 1:
                              location_span(backbone["receiver_overhangs"]["3_prime"]["location"])[1]]
    left, right = level2_overhang("0.5rc", "level2_C"), level2_overhang("0.1", "level2_N")
    seq = n1 + left + promoter_seq + right + c1
    end = len(seq)
    overhangs = [
        {"start": 1, "end": 4, "label": "NLvl1", "role": "level1_N"},
        {"start": 5, "end": 8, "label": "Lvl2 junction cargo | promoter", "role": "level2_N"},
        {"start": end - 7, "end": end - 4, "label": "Lvl2 junction promoter | NC", "role": "level2_C"},
        {"start": end - 3, "end": end, "label": "CLvl1", "role": "level1_C"},
    ]
    parts = [{"label": label, "type": "Promoter", "start": 9, "end": end - 8, "strand": "sense", "kind": "promoter",
              "isReal": is_real, "isUser": False, "what": "bidirectional promoter",
              "note": "bidirectional promoter · toolkit part" + ("" if is_real else " · PLACEHOLDER sequence")}]
    notes = [] if is_real else [f"PLACEHOLDER sequence (not in the parts database yet): {label}"]
    out = _pack(label, "Level 1 promoter", "promoter", "bidirectional", seq, parts, overhangs, notes, [], name)
    return out


def _site_intact(new_seq: str, location: str, enzyme: str) -> bool:
    a, b = location_span(location)
    site = new_seq[a - 1:b]
    return (reverse_complement(site) if location.startswith("complement(") else site) == SITES[enzyme][0]


def clone_fragment_into_backbone(backbone: dict, fragment: str, features: list, name: str, what: str,
                                 keep_label: str | None = None, keep_enzyme: str | None = None) -> dict:
    """Replaces in `backbone` everything from the NLvl overhang up to and including the CLvl overhang by `fragment` (which begins/ends
    with exactly these two overhangs). Backbone features outside stay (shifted behind the insert);
    features in the replaced region disappear with the stuffer. Recognition sites with `keep_label`
    reach into the region at the seam and are kept; backbone and fragment together build their bases;
    they are checked for integrity afterwards. `features` are relative to the fragment."""
    seq = backbone["sequence"]
    oh5, oh3 = backbone["receiver_overhangs"]["5_prime"], backbone["receiver_overhangs"]["3_prime"]
    n0, n1 = location_span(oh5["location"])
    c0, c1 = location_span(oh3["location"])
    if fragment[:4] != seq[n0 - 1:n1] or fragment[-4:] != seq[c0 - 1:c1]:
        raise ValueError(f"The overhangs of the fragment ({fragment[:4]}/{fragment[-4:]}) do not match "
                         f"{backbone['id']} ({seq[n0 - 1:n1]}/{seq[c0 - 1:c1]}).")
    new_seq = seq[:n0 - 1] + fragment + seq[c1:]
    tail_shift = len(fragment) - (c1 - n0 + 1)

    out = []
    for f in backbone.get("features", []):
        lo, hi = location_span(f["location"])
        label = (f["qualifiers"].get("label") or [""])[0]
        loc = None
        if f["type"] == "source":
            loc = f"1..{len(new_seq)}"
        elif hi < n0:
            loc = f["location"]
        elif lo > c1:
            loc = shift_location(f["location"], tail_shift)
        elif keep_label and label == keep_label and (lo < n0 or hi > c1):
            loc = f["location"] if lo < n0 else shift_location(f["location"], tail_shift)
            if not _site_intact(new_seq, loc, keep_enzyme):
                raise ValueError(f"{keep_enzyme} site {loc} is not intact after cloning.")
        if loc is not None:
            quals = [(k, v) for k, vals in f["qualifiers"].items() if k != "translation" for v in vals]
            out.append({"type": f["type"], "location": loc, "qualifiers": quals})
    for f in features:
        out.append({**f, "location": shift_location(f["location"], n0 - 1)})
    out.sort(key=lambda f: (location_span(f["location"])[0], location_span(f["location"])[1]))
    for f in out:
        a, b = location_span(f["location"])
        if a < 1 or b > len(new_seq):
            raise ValueError(f"Feature {f['location']} lies outside the plasmid.")

    definition = (f"{backbone['label']} with {what}: the {c1 - n0 + 1} bp between {oh5['label']} and {oh3['label']} "
                  f"(stuffer / test cassette) replaced by {len(fragment)} bp.")
    return {"name": name, "sequence": new_seq, "length": len(new_seq), "insertStart": n0,
            "insertEnd": n0 + len(fragment) - 1,
            "genbank": format_genbank_record(name, new_seq, out, True, definition)}


def rotated_view(module: dict) -> dict:
    """The same Level 1 insert rotated by 180 degrees (reverse complement, positions mirrored, strand flipped), so that
    the cargo module reads in its own direction (5' left -> 3' right, Type 0.5 ... 0.1). For display only
    and for the insert download; plasmid and Level 2 assembly stay in top strand orientation."""
    seq, n = module["sequence"], module["length"]
    rseq = reverse_complement(seq)

    def flip(a: int, b: int) -> tuple:
        return n - b + 1, n - a + 1

    parts = []
    for p in reversed(module["parts"]):
        a, b = flip(p["start"], p["end"])
        parts.append({**p, "start": a, "end": b, "strand": "sense" if p["strand"] == "antisense" else "antisense"})
    overhangs = []
    for o in reversed(module["overhangs"]):
        a, b = flip(o["start"], o["end"])
        overhangs.append({**o, "start": a, "end": b, "sequence": rseq[a - 1:b]})
    spacers = []
    for sp in reversed(module["spacers"]):
        a, b = flip(sp["start"], sp["end"])
        spacers.append({**sp, "start": a, "end": b})
    feats = [_overhang_feature(o, rseq) for o in overhangs] + [_spacer_feature(sp) for sp in spacers]
    for p in parts:
        feats.append(make_feature("CDS", _loc(p["start"], p["end"], p["strand"] == "antisense"), p["label"], p["note"]))
    feats.sort(key=lambda f: location_span(f["location"])[0])
    definition = (f"{module['what']} (antisense strand module), shown rotated by 180 degrees relative to the Level 1 plasmid top "
                  f"strand so the cargo reads 5'->3' left to right: Level 0 parts joined via BsaI overhangs, flanked by the "
                  f"reverse complements of CLvl1 and NLvl1." + (" " + " ".join(module["notes"]) if module["notes"] else ""))
    return {
        "sequence": rseq, "length": n, "parts": parts, "overhangs": overhangs, "spacers": spacers,
        "level2Overhangs": {"n": rseq[4:8], "c": rseq[-8:-4]},
        "genbank": format_genbank_record(module["name"], rseq, feats, False, definition),
    }


def finish_level1(module: dict, backbone: dict | None) -> dict:
    """Insert record (linear) and, if the Level 1 backbone is there, the plasmid with BsaI cloning."""
    definition = (f"{module['what']}: Level 0 parts joined via BsaI overhangs, flanked by NLvl1 (ACAT) and CLvl1 (TTGT); "
                  f"Level 2 overhangs {module['level2Overhangs']['n']} / {module['level2Overhangs']['c']}. "
                  + ("Sequence 5'->3' left to right = Level 1 plasmid top strand"
                     + ("; the cargo ORF is antisense on it." if module["strand"] == "antisense" else "."))
                  + (" " + " ".join(module["notes"]) if module["notes"] else ""))
    feats = module.pop("_features")
    module["genbank"] = format_genbank_record(module["name"], module["sequence"], feats, False, definition)
    # Cargo module: display/insert download rotated (cargo in reading direction), as for Level 0
    module["shown"] = rotated_view(module) if module["strand"] == "antisense" else None
    module["plasmid"] = None
    if backbone:
        module["plasmid"] = clone_fragment_into_backbone(
            backbone, module["sequence"], feats, f"pAGM1311_{module['name']}",
            f"{module['label']} assembled via BsaI", keep_label="BbsI rec site", keep_enzyme="BbsI")
    return module


def assemble_level2(modules: list, name: str, backbone: dict | None) -> dict:
    """Cargo module, promoter and NC module (Level 1 inserts, in this order) into the Level 2 insert: from every
    Level 1 insert the piece between the Level 2 overhangs is cut by BbsI (NLvl1/CLvl1 drop out),
    the three pieces ligate through CGTT and TGAT; the ends (CCAA / AATG) match BbLvl2N/BbLvl2C."""
    seq, parts, inner, ends, spacers = "", [], [], [], []
    for k, m in enumerate(modules):
        frag = m["sequence"][4:-4]
        if k == 0:
            base, seq = 0, frag
        else:
            if seq[-4:] != frag[:4]:
                raise ValueError(f"Level 2: overhang {frag[:4]} of {m['label']} does not match the predecessor ({seq[-4:]}).")
            base = len(seq) - 4
            seq += frag[4:]
        shift = base - 4                                  # Level 1 coordinate -> Level 2 coordinate
        ends.append(len(seq))  # end of this piece in the Level 2 insert
        for p in m["parts"]:
            parts.append({**p, "start": p["start"] + shift, "end": p["end"] + shift, "module": m["site"]})
        for sp in m["spacers"]:
            spacers.append({**sp, "start": sp["start"] + shift, "end": sp["end"] + shift})
        for o in m["overhangs"]:
            if o["role"] in ("level1_N", "level1_C") and o["start"] >= 5 and o["end"] <= len(m["sequence"]) - 4:
                inner.append({"start": o["start"] + shift, "end": o["end"] + shift, "label": o["label"], "role": o["role"]})
    end = len(seq)
    j1, j2 = ends[0], ends[1]
    overhangs = _merge_overhangs(inner + [
        {"start": 1, "end": 4, "label": "BbLvl2N", "role": "level2_N"},
        {"start": j1 - 3, "end": j1, "label": "Lvl2 junction cargo module | promoter", "role": "level2_N"},
        {"start": j2 - 3, "end": j2, "label": "Lvl2 junction promoter | NC module", "role": "level2_N"},
        {"start": end - 3, "end": end, "label": "BbLvl2C", "role": "level2_C"}])
    feats = [_overhang_feature(o, seq) for o in overhangs] + [_spacer_feature(sp) for sp in spacers]
    for p in parts:
        feats.append(make_feature("promoter" if p["kind"] == "promoter" else "CDS",
                                  _loc(p["start"], p["end"], p["strand"] == "antisense"), p["label"], p["note"]))
    feats.sort(key=lambda f: location_span(f["location"])[0])
    notes = [n for m in modules for n in m["notes"]]
    junctions = {"n": seq[:4], "cargoPromoter": seq[j1 - 4:j1], "promoterNc": seq[j2 - 4:j2], "c": seq[-4:]}
    definition = (f"Level 2 insert: cargo module (antisense) <- promoter -> nanocompartment module (sense), assembled via "
                  f"BbsI from the three Level 1 plasmids. Ends {junctions['n']} / {junctions['c']} match BbLvl2N / BbLvl2C of "
                  f"the Level 2 backbone; junctions {junctions['cargoPromoter']} (cargo | promoter) and "
                  f"{junctions['promoterNc']} (promoter | NC)." + (" " + " ".join(notes) if notes else ""))
    out = {"name": name, "sequence": seq, "length": len(seq), "parts": parts,
           "overhangs": [{"label": o["label"], "start": o["start"], "end": o["end"], "role": o["role"],
                          "sequence": seq[o["start"] - 1:o["end"]]} for o in overhangs],
           "junctions": junctions, "notes": notes,
           "genbank": format_genbank_record(f"Level2_{name}", seq, feats, False, definition), "plasmid": None}
    if backbone:
        out["plasmid"] = clone_fragment_into_backbone(backbone, seq, feats, f"pESC-HIS_Level2_{name}",
                                                      "the assembled Level 2 insert (BbsI)")
    return out
