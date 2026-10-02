from __future__ import annotations

"""Level-1- und Level-2-Assemblierung per Golden Gate.

Level 0 -> 1 (BsaI): BsaI schneidet aus jedem Level-0-Plasmid das Fragment vom Level-1-N- bis zum Level-1-C-
Overhang (= Teil + Level-1-Overhangs, bei Type 0.1/0.5 zusaetzlich die Level-2-Overhangs). Die fuenf Fragmente
eines Moduls ligieren ueber ihre gemeinsamen Overhangs (ACAT | TATG | TTCT | ATCC | TGGC | TTGT) und landen
zwischen den Akzeptor-Overhangs NLvl1/CLvl1 des Level-1-Backbones (pAGM1311).

Level 1 -> 2 (BbsI): BbsI schneidet aus den drei Level-1-Plasmiden (Cargo-Modul, Promotor, NC-Modul) das Stueck
zwischen den Level-2-Overhangs (CCAA ... CGTT | CGTT ... TGAT | TGAT ... AATG) und ligiert es zwischen BbLvl2N/
BbLvl2C des Level-2-Backbones (pESC-HIS).

Alle Sequenzen sind der Top-Strand, 5' links -> 3' rechts. Das Cargo-Modul liegt darauf antisense (jedes Teil als
Reverse Complement), die zugehoerigen CDS-Features tragen deshalb complement()."""

from .genbank_writer import format_genbank_record, location_span, make_feature, shift_location
from .parts_db import find_part
from .sequence import reverse_complement

SITES = {"BsaI": ("GGTCTC", "GAGACC"), "BbsI": ("GAAGAC", "GTCTTC")}


def _loc(start: int, end: int, antisense: bool = False) -> str:
    span = f"{start}..{end}"
    return f"complement({span})" if antisense else span


def level1_fragment(built: dict) -> dict:
    """Das BsaI-Fragment eines Level-0-Konstrukts (`attach_adapter`-Ergebnis in Plasmid-Orientierung): vom
    Level-1-N-Overhang bis einschliesslich Level-1-C-Overhang. Koordinaten relativ zum Fragment (1-basiert)."""
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
    """Overhang-Features gleicher Position (Naht zweier Fragmente) zu einem zusammenfassen, Labels mit ' / '."""
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
    """Gemeinsame Gestalt eines Level-1-Inserts (auch fuer den Promotor)."""
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
    """Fuenf Level-0-Fragmente (Type 0.1 ... 0.5) zu einem Level-1-Insert. `fragments`: Eintraege mit
    "fragment" (level1_fragment), "label", "type", "isReal", "isUser", "what", "insertSequence"."""
    seq, parts, overhangs, sites, placeholders, spacers = "", [], [], [], [], []
    for k, fr in enumerate(fragments):
        f = fr["fragment"]
        if k == 0:
            base = 0
            seq = f["sequence"]
        else:
            if seq[-4:] != f["sequence"][:4]:
                raise ValueError(f"{fr['type']}: Overhang {f['sequence'][:4]} passt nicht zum Vorgaenger ({seq[-4:]}).")
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
    """Top-Strand-Basen des Level-2-Overhangs eines Adapters (z.B. ("0.5rc", "level2_C") -> CGTT)."""
    entry = find_part("type_overhangs", adapter_id)
    for o in entry["overhangs"]:
        if o["role"] == role:
            return o["sequence_top_strand"]
    raise ValueError(f"Adapter {adapter_id} hat keinen {role}-Overhang.")


def assemble_level1_promoter(label: str, promoter_seq: str, is_real: bool, name: str, backbone: dict) -> dict:
    """Promotor-Insert fuer Level 1: NLvl1 + Level-2-N-Overhang (= C-Overhang des Cargo-Moduls) + Promotor +
    Level-2-C-Overhang (= N-Overhang des NC-Moduls) + CLvl1."""
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
    """Ersetzt in `backbone` alles von NLvl-Overhang bis einschliesslich CLvl-Overhang durch `fragment` (das mit
    genau diesen beiden Overhangs beginnt/endet). Backbone-Features ausserhalb bleiben (hinter dem Insert
    verschoben); Features im ersetzten Bereich entfallen mit dem Stuffer. Erkennungsstellen mit `keep_label`
    ragen an der Naht in den Bereich hinein und bleiben erhalten — ihre Basen setzen Backbone und Fragment
    gemeinsam zusammen; sie werden danach auf Unversehrtheit geprueft. `features` liegen relativ zum Fragment."""
    seq = backbone["sequence"]
    oh5, oh3 = backbone["receiver_overhangs"]["5_prime"], backbone["receiver_overhangs"]["3_prime"]
    n0, n1 = location_span(oh5["location"])
    c0, c1 = location_span(oh3["location"])
    if fragment[:4] != seq[n0 - 1:n1] or fragment[-4:] != seq[c0 - 1:c1]:
        raise ValueError(f"Die Overhangs des Fragments ({fragment[:4]}/{fragment[-4:]}) passen nicht zu "
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
                raise ValueError(f"{keep_enzyme}-Stelle {loc} ist nach dem Klonieren nicht intakt.")
        if loc is not None:
            quals = [(k, v) for k, vals in f["qualifiers"].items() if k != "translation" for v in vals]
            out.append({"type": f["type"], "location": loc, "qualifiers": quals})
    for f in features:
        out.append({**f, "location": shift_location(f["location"], n0 - 1)})
    out.sort(key=lambda f: (location_span(f["location"])[0], location_span(f["location"])[1]))
    for f in out:
        a, b = location_span(f["location"])
        if a < 1 or b > len(new_seq):
            raise ValueError(f"Feature {f['location']} liegt ausserhalb des Plasmids.")

    definition = (f"{backbone['label']} with {what}: the {c1 - n0 + 1} bp between {oh5['label']} and {oh3['label']} "
                  f"(stuffer / test cassette) replaced by {len(fragment)} bp.")
    return {"name": name, "sequence": new_seq, "length": len(new_seq), "insertStart": n0,
            "insertEnd": n0 + len(fragment) - 1,
            "genbank": format_genbank_record(name, new_seq, out, True, definition)}


def rotated_view(module: dict) -> dict:
    """Dasselbe Level-1-Insert um 180 Grad gedreht (Reverse Complement, Positionen gespiegelt, Strang gekippt), damit
    das Cargo-Modul in seiner eigenen Leserichtung steht (5' links -> 3' rechts, Type 0.5 ... 0.1). Nur zur Anzeige
    und fuer den Insert-Download; Plasmid und Level-2-Assemblierung bleiben in der Top-Strand-Orientierung."""
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
    """Insert-Record (linear) und, falls das Level-1-Backbone da ist, das Plasmid mit BsaI-Klonierung."""
    definition = (f"{module['what']}: Level 0 parts joined via BsaI overhangs, flanked by NLvl1 (ACAT) and CLvl1 (TTGT); "
                  f"Level 2 overhangs {module['level2Overhangs']['n']} / {module['level2Overhangs']['c']}. "
                  + ("Sequence 5'->3' left to right = Level 1 plasmid top strand"
                     + ("; the cargo ORF is antisense on it." if module["strand"] == "antisense" else "."))
                  + (" " + " ".join(module["notes"]) if module["notes"] else ""))
    feats = module.pop("_features")
    module["genbank"] = format_genbank_record(module["name"], module["sequence"], feats, False, definition)
    # Cargo-Modul: Anzeige/Insert-Download gedreht (Cargo in Leserichtung), wie bei Level 0
    module["shown"] = rotated_view(module) if module["strand"] == "antisense" else None
    module["plasmid"] = None
    if backbone:
        module["plasmid"] = clone_fragment_into_backbone(
            backbone, module["sequence"], feats, f"pAGM1311_{module['name']}",
            f"{module['label']} assembled via BsaI", keep_label="BbsI rec site", keep_enzyme="BbsI")
    return module


def assemble_level2(modules: list, name: str, backbone: dict | None) -> dict:
    """Cargo-Modul, Promotor und NC-Modul (Level-1-Inserts, in dieser Reihenfolge) zum Level-2-Insert: aus jedem
    Level-1-Insert wird per BbsI das Stueck zwischen den Level-2-Overhangs geschnitten (NLvl1/CLvl1 entfallen),
    die drei Stuecke ligieren ueber CGTT bzw. TGAT; die Enden (CCAA / AATG) passen zu BbLvl2N/BbLvl2C."""
    seq, parts, inner, ends, spacers = "", [], [], [], []
    for k, m in enumerate(modules):
        frag = m["sequence"][4:-4]
        if k == 0:
            base, seq = 0, frag
        else:
            if seq[-4:] != frag[:4]:
                raise ValueError(f"Level 2: Overhang {frag[:4]} von {m['label']} passt nicht zum Vorgaenger ({seq[-4:]}).")
            base = len(seq) - 4
            seq += frag[4:]
        shift = base - 4                                  # Level-1-Koordinate -> Level-2-Koordinate
        ends.append(len(seq))                             # Ende dieses Stuecks im Level-2-Insert
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
