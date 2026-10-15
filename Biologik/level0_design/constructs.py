"""The Level 0 construct of each of the ten modules: part sequence in the adapter, plasmid, primers, oligos and GenBank."""

from __future__ import annotations

from typing import NamedTuple

from .adapters import adapter_id_for, attach_adapter, rotate_built, spacer_mode
from .assembly import level1_fragment
from .cloning import clone_into_level0_backbone
from .data import NOMINAL_BP, STOP_CODONS
from .genbank_writer import format_genbank_record, level0_record_name, location_span, make_feature as _feat
from .oligos import design_level0_oligos
from .parts_db import plasmid_status, bare_cds, find_inserts, find_library_cargo, find_real_sequence, load_parts
from .primers import MIN_PCR_INSERT_BP, design_level0_primers, pcr_product_genbank
from .sequence import reverse_complement
from .slots import COMBINED_NCS, module_units, orf_slots
from .user_codons import codon_note


def placeholder_seq(seed: str, length: int) -> str:
    bases = "ATGC"
    value = 0
    for char in seed:
        value = (value * 31 + ord(char)) & 0xFFFFFFFF
    result = []
    for _ in range(length):
        value = (value * 1103515245 + 12345) & 0xFFFFFFFF
        result.append(bases[(value >> 16) % 4])
    return "".join(result)


def resolve_seq(kind: str, part_id: str, seed: str, length: int) -> tuple[str, bool]:
    """(sequence, is_real). Uses a real sequence from the parts database
    (Biologik/level0_design/parts/<kind>/<part_id>.json) if one is stored there with
    sequence_status "real"; otherwise it falls back to the earlier
    deterministic placeholder sequence. As soon as someone fills in the JSON file,
    the next request automatically uses the real sequence."""
    real = find_real_sequence(kind, part_id)
    if real:
        return real, True
    return placeholder_seq(seed, length), False


def resolve_insert(category: str, part: str, site: str, slot: int, seed: str, length: int, **extra) -> tuple:
    """(part sequence in sense direction, is_real, entry of the Level 0 plasmid or None) of a toolkit part for a site
    ("nc_site"/"cargo_site") and a Type slot from the database parts/level0_inserts/. If there is a Level 0 plasmid exactly
    there, its insert and entry are used. Otherwise the sequence of the same part from another site/slot (entry None: there
    is no plasmid at this position), and without any hit a deterministic placeholder sequence."""
    exact = find_inserts(category, part, site, slot, **extra)
    if exact:
        return exact[0]["sequence"], True, exact[0]
    other = find_inserts(category, part, site, **extra) or find_inserts(category, part, **extra)
    if other:
        return other[0]["sequence"], True, None
    return placeholder_seq(seed, length), False, None


class Part(NamedTuple):
    """A part of a module before it goes into its adapter. `seq` is the sense sequence (for the cargo only known later);
    `is_user` = entered by the user instead of a toolkit part, `is_real` = real sequence instead of a placeholder, `source` = entry
    of the Level 0 plasmid in the database (it carries the iGEM Registry link of a toolkit part)."""
    label: str
    seq: str | None
    is_real: bool
    is_user: bool
    what: str
    source: dict | None


def _toolkit_part(cfg: dict, nc: dict, site: str, n: int) -> Part:
    """The part in slot `n` of a site: the user's own sequence or the chosen toolkit part from the database."""
    kind = cfg["kind"]
    if kind == "custom":
        return Part(cfg["label"], cfg["seq"], True, True, "your own part", None)
    if kind == "tp":
        found = resolve_insert("tp", nc["tp"], site, n, "TP" + nc["tp"], NOMINAL_BP["TP"])
        return Part(nc["tp"], found[0], found[1], False, "targeting peptide (toolkit part)", found[2])
    if kind == "linker":
        found = resolve_insert("linker", cfg["id"], site, n, "LINK" + cfg["id"], cfg["bp"])
        return Part(cfg["label"], found[0], found[1], False, "linker (toolkit part)", found[2])
    if kind == "marker":
        found = resolve_insert("marker", cfg["id"], site, n, "MARK" + cfg["id"], cfg["bp"])
        return Part(cfg["label"], found[0], found[1], False, "surface marker (toolkit part)", found[2])
    if kind == "intein":
        found = resolve_insert("intein", cfg["id"], site, n, "INT" + cfg["id"], cfg["bp"])
        return Part(cfg["label"], found[0], found[1], False, "intein (toolkit part)", found[2])
    if kind in COMBINED_NCS:
        a, b = COMBINED_NCS[kind]
        found = resolve_insert("ncs", "ncs", site, None, "NCS", 30, covers_slots=[a, b])
        return Part("NCS", found[0], found[1], False, f"combined NCS spacer, replaces Type 0.{a} and 0.{b} (toolkit part)", found[2])
    found = resolve_insert("ncs", "ncs", site, n, "NCS", 30)
    return Part("NCS", found[0], found[1], False, "NCS spacer (toolkit part)", found[2])


def _middle_parts(nc: dict, cargo_label: str, cargo_antisense: str) -> tuple:
    """(shell, cargo) as parts of Type 0.3. An own shell and an own cargo are user inputs; if the cargo comes
    unchanged from the cargo library it is a toolkit part. The cargo sequence is only inserted later
    (as antisense)."""
    if nc.get("custom"):
        shell = Part(nc["shell"], nc["seq"], True, True, "your own nanocompartment shell", None)
    else:
        found = resolve_insert("shell", nc["shell"], "nc_site", 3, "SHELL" + nc["shell"], nc["shellBp"])
        shell = Part(nc["shell"], found[0], found[1], False, "nanocompartment shell (toolkit part)", found[2])
    preset = find_library_cargo(reverse_complement(cargo_antisense))
    cargo = Part(cargo_label, None, True, preset is None, "cargo gene of interest" if preset is None else "cargo (toolkit part)",
                 preset)
    return shell, cargo


def _orf_flags(slots: dict, module: str) -> dict:
    """{slot: (start, stop)} for the coding parts of a module: the first coding part in reading direction gets the start codon (ATG),
    the last one a stop codon, wherever it sits (also the central part, if every part behind it is an NCS spacer). NCS spacers get
    neither. Reading direction: NC module Type 0.1 -> 0.5, cargo module (antisense) Type 0.5 -> 0.1; the central part (Type 0.3) is
    always coding."""
    coding = orf_slots(slots, module)
    return {n: (n == coding[0], n == coding[-1]) for n in coding}


def _add_start_stop(seq: str, start: bool, stop: bool, is_user: bool) -> str:
    """Start codon in front and stop codon behind a sense CDS. A toolkit part is stored bare, so it always gets them; an own
    sequence may already carry an ATG or a stop codon, then nothing is doubled."""
    if start and not (is_user and seq.startswith("ATG")):
        seq = "ATG" + seq
    if stop and not (is_user and seq[-3:] in STOP_CODONS):
        seq += "TAA"
    return seq


def _mark_stop(built: dict, sense: str, module: str) -> None:
    """Mark the stop codon at the 3' end of the ORF (the last codon of the sense sequence) as an entry in `built["stops"]`."""
    off = len(sense) - 3
    ia, ib = location_span(built["insert"]["location"])
    a = ia + off if module == "nc" else ib - off - 2
    built["stops"].append({"location": f"{a}..{a + 2}", "note": f"stop codon {sense[off:]} in the reading frame of the ORF"})


def _construct_features(shown: dict, part: Part, n: int, adapter_id: str, orientation: str, codon: dict | None) -> list:
    """Annotations of the construct (as it is displayed): BbsI sites, overhangs, frame spacer, stop codon and the insert."""
    features = [_feat("misc_feature", b["location"], "BbsI rec site") for b in shown["bbsiSites"]]
    features += [_feat("overhang", o["location"], o["label"], f"{o['role']} · top strand {o['sequence_top_strand']}")
                 for o in shown["overhangs"]]
    features += [_feat("misc_feature", sp["location"], "Frame spacer", sp["note"]) for sp in shown["spacers"]]
    features += [_feat("misc_feature", st["location"], "Stop codon", st["note"]) for st in shown["stops"]]
    features.append(_feat("CDS", shown["insert"]["location"], part.label,
                          f"Type 0.{n} · {part.what} · {orientation} · adapter {adapter_id}"
                          + (f" · {codon_note(codon)}" if codon else "")))
    return features


def _ordering_options(part: Part, built: dict, shown: dict, n: int, module: str, adapter_id: str, features: list) -> tuple:
    """(primers, oligo pair) of a part. Primers exist only for own sequences (which one wants to build into the toolbox) and only
    if they are long enough for PCR; toolkit parts are ordered as DNA/oligos. Every part
    with a real sequence below MIN_PCR_INSERT_BP gets an oligo pair, whether own input or toolkit part.
    The primer binding sites are added to `features` as features."""
    if not part.is_real:
        primers = {"possible": False, "reason": "No real sequence in the parts database yet; primers can only be designed for a real sequence."}
    elif not part.is_user:
        primers = {"possible": False, "reason": "Toolbox part: order it as DNA; primers are only designed for your own sequences."}
    else:
        primers = design_level0_primers(shown, part.label, n, module)
    oligos = (design_level0_oligos(built, part.label, n, module)
              if part.is_real and len(built["insert"]["sequence"]) < MIN_PCR_INSERT_BP else None)
    if primers["possible"]:
        primers["genbank"] = pcr_product_genbank(shown, primers, part.label, n, module, adapter_id, list(features))
        i_start, i_end = location_span(shown["insert"]["location"])
        for key, loc in (("forward", f"{i_start}..{i_start + primers['forward']['annealLength'] - 1}"),
                         ("reverse", f"complement({i_end - primers['reverse']['annealLength'] + 1}..{i_end})")):
            features.append(_feat("primer_bind", loc, primers[key]["name"],
                                  f"annealing part of {primers[key]['name']} (Tm {primers[key]['tm']} °C)"))
    return primers, oligos


def _definition(label: str, adapter_id: str, antisense: bool, is_real: bool) -> str:
    site = "cargo" if antisense else "nanocompartment"
    strand = ("antisense strand (cargo module); shown rotated 180 degrees relative to the Level 0 plasmid top strand"
              if antisense else "sense strand")
    text = f"Level 0 construct for the {site} site: {label} in adapter {adapter_id} (BbsI). Sequence 5'->3' left to right, {strand}."
    return text if is_real else text + " PLACEHOLDER insert: the real sequence is not in the parts database yet."


def _build_construct(part: Part, module: str, n: int, codon: dict | None, backbone: dict | None, cargo_antisense: str,
                     start: bool = False, stop: bool = False) -> tuple:
    """The Level 0 construct of Type 0.`n` of module `module` and the BsaI fragment of this part for Level 1.
    Start and stop codon are added here per slot (`start`/`stop`, see `_orf_flags`). Cargo module parts sit on the antisense
    strand and are inserted as a reverse complement; the cargo site is displayed rotated by 180 degrees so that the cargo reads in its own
    reading direction (5' left -> 3' right)."""
    antisense = module == "cargo"
    sense = part.seq
    if antisense and n == 3:
        sense = reverse_complement(cargo_antisense)
        if not part.is_user:
            sense = bare_cds(sense)  # a library cargo entered with its ATG / stop codon: the start and stop are added below
    sense = _add_start_stop(sense, start, stop, part.is_user)
    seq = reverse_complement(sense) if antisense else sense
    adapter_id = adapter_id_for(module, n)
    built = attach_adapter(adapter_id, seq, spacer_mode(module, n))  # top strand of the Level 0 plasmid, 5' left -> 3' right
    built["stops"] = []
    if stop:
        _mark_stop(built, sense, module)
    plasmid = clone_into_level0_backbone(
        built, part.label, backbone, antisense,
        f"{backbone['id'].split('-')[0]}_{level0_record_name(part.label, n, module)}") if backbone else None
    fragment = {"module": module, "slot": n, "label": part.label, "type": f"Type 0.{n}", "what": part.what,
                "isReal": part.is_real, "isUser": part.is_user, "fragment": level1_fragment(built),
                "insertSequence": built["insert"]["sequence"]}

    shown = rotate_built(built) if antisense else built
    orientation = ("antisense strand (cargo module): shown 5'->3' left to right, rotated 180° vs. the Level 0 plasmid top strand"
                   if antisense else "sense strand: as entered")
    features = _construct_features(shown, part, n, adapter_id, orientation, codon)
    primers, oligos = _ordering_options(part, built, shown, n, module, adapter_id, features)
    features.sort(key=lambda f: location_span(f["location"])[0])
    record_name = level0_record_name(part.label, n, module)
    construct = {
        "label": part.label, "what": part.what, "module": "cargo_site" if antisense else "nc_site",
        "slot": n, "type": f"Type 0.{n}", "orientation": orientation,
        "strand": "antisense" if antisense else "sense", "rotated": antisense,
        "plasmidStrand": "antisense" if antisense else "sense",
        "isUser": part.is_user, "isReal": part.is_real,
        "adapter": built["adapter"], "usedForModules": built["usedForModules"],
        "sequence": shown["sequence"], "length": shown["length"], "insert": shown["insert"],
        "overhangs": shown["overhangs"], "bbsiSites": shown["bbsiSites"],
        "primers": primers, "oligos": oligos,
        # link to the part in the iGEM Registry (parts database field `registry_url`); None until it is filled in, and for own parts
        "registryUrl": None if part.is_user or not part.source else part.source.get("registry_url"),
        # state of the Level 0 plasmid of a toolkit part: "built" or "not_built" (None for your own sequences); stock is not considered
        "plasmidStatus": None if part.is_user else plasmid_status(part.source),
        "codon": codon if part.is_user else None,
        "stopCodon": bool(shown["stops"]), "stopLocation": shown["stops"][0]["location"] if shown["stops"] else None,
        "genbank": format_genbank_record(record_name, shown["sequence"], features, False,
                                         _definition(part.label, adapter_id, antisense, part.is_real)),
        "plasmid": plasmid,
    }
    return construct, fragment


def build_level0_constructs(nc: dict, cargo_label: str, cargo_antisense: str, cargo_slots: dict, nc_slots: dict,
                            fragments: list | None = None, cargo_codon: dict | None = None) -> list:
    """The Level 0 construct of each of the ten modules (cargo site + NC site, Type 0.1-0.5): the part sequence in the
    overhang adapter of its Type slot (attach_adapter) and, if the Level 0 backbone is in the database,
    the plasmid cloned from it by BbsI (clone_into_level0_backbone), each with a finished GenBank text.

    `isUser` = entered by the user (cargo, own shell/parts), otherwise toolkit part; `isReal` = real
    sequence (user input or parts database) instead of a deterministic placeholder. The BsaI fragments of all parts
    (for the Level 1 assembly) go into `fragments` if it is passed."""
    shell, cargo = _middle_parts(nc, cargo_label, cargo_antisense)
    backbone = next(iter(load_parts()["level0_backbones"]), None)
    if backbone and not backbone.get("sequence"):
        backbone = None

    constructs = []
    for module, slots, middle in (("cargo", cargo_slots, cargo), ("nc", nc_slots, shell)):
        site = "cargo_site" if module == "cargo" else "nc_site"
        flags = _orf_flags(slots, module)
        for n, covers in module_units(slots):
            part = middle if n == 3 else _toolkit_part(slots[covers[0]], nc, site, covers[0])
            codon = (cargo_codon if module == "cargo" else nc.get("codon")) if n == 3 else slots[covers[0]].get("codon")
            construct, fragment = _build_construct(part, module, n, codon, backbone, cargo_antisense, *flags.get(n, (False, False)))
            constructs.append(construct)
            if fragments is not None:
                fragments.append(fragment)
    return constructs
