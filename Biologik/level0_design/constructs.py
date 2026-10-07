"""Das Level-0-Konstrukt jedes der zehn Module: Teilsequenz im Adapter, Plasmid, Primer, Oligos und GenBank."""

from __future__ import annotations

from typing import NamedTuple

from .adapters import adapter_id_for, attach_adapter, rotate_built
from .assembly import level1_fragment
from .cloning import clone_into_level0_backbone
from .data import NOMINAL_BP, STOP_CODONS
from .genbank_writer import format_genbank_record, level0_record_name, location_span, make_feature as _feat
from .oligos import design_level0_oligos
from .parts_db import find_inserts, find_library_cargo, find_real_sequence, load_parts
from .primers import MIN_PCR_INSERT_BP, design_level0_primers, pcr_product_genbank
from .sequence import reverse_complement
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
    """(sequence, is_real). Nutzt eine echte Sequenz aus der Teile-Datenbank
    (Biologik/level0_design/parts/<kind>/<part_id>.json), falls dort mit
    sequence_status "real" hinterlegt — sonst faellt es auf die bisherige
    deterministische Platzhalter-Sequenz zurueck. Sobald jemand die JSON-Datei
    ausfuellt, verwendet der naechste Request automatisch die echte Sequenz."""
    real = find_real_sequence(kind, part_id)
    if real:
        return real, True
    return placeholder_seq(seed, length), False


def resolve_insert(category: str, part: str, site: str, slot: int, seed: str, length: int, **extra) -> tuple:
    """(Teilsequenz in Sense-Richtung, ist_echt, Lagerstatus, Eintrag des Level-0-Plasmids oder None) eines Toolkit-Teils fuer eine Site ("nc_site"/"cargo_site") und
    einen Type-Slot aus der Datenbank parts/level0_inserts/. Gibt es genau dort ein Level-0-Plasmid, kommt dessen Insert und
    sein Lagerstatus (on_stock). Sonst die Sequenz desselben Teils von einer anderen Site/einem anderen Slot (Lagerstatus
    False: an dieser Stelle gibt es kein Plasmid), und ohne jeden Treffer eine deterministische Platzhalter-Sequenz."""
    exact = find_inserts(category, part, site, slot, **extra)
    if exact:
        return exact[0]["sequence"], True, exact[0].get("on_stock"), exact[0]
    other = (find_inserts(category, part, site, **extra) or find_inserts(category, part, **extra)
             or (find_inserts(category, part, site) or find_inserts(category, part) if "variant" not in extra else []))
    if other:
        return other[0]["sequence"], True, False, None
    return placeholder_seq(seed, length), False, None, None


def first_stop_offset(sense: str):
    """Offset (0-basiert) des ersten Stopcodons (TAA/TAG/TGA) im Leseraster einer Sense-Sequenz, sonst None."""
    for i in range(0, len(sense) - 2, 3):
        if sense[i:i + 3] in STOP_CODONS:
            return i
    return None


class Part(NamedTuple):
    """Ein Teil eines Moduls, bevor es in seinen Adapter kommt. `seq` ist die Sense-Sequenz (beim Cargo erst spaeter bekannt);
    `is_user` = vom Nutzer eingegeben statt Toolkit-Teil, `is_real` = echte Sequenz statt Platzhalter, `source` = Eintrag
    des Level-0-Plasmids in der Datenbank."""
    label: str
    seq: str | None
    is_real: bool
    is_user: bool
    what: str
    on_stock: bool | None
    source: dict | None


def _toolkit_part(cfg: dict, nc: dict, site: str, n: int) -> Part:
    """Das Teil in Slot `n` einer Site: die eigene Sequenz des Nutzers oder das gewaehlte Toolkit-Teil aus der Datenbank."""
    kind = cfg["kind"]
    if kind == "custom":
        return Part(cfg["label"], cfg["seq"], True, True, "your own part", None, None)
    if kind == "tp":
        found = resolve_insert("tp", nc["tp"], site, n, "TP" + nc["tp"], NOMINAL_BP["TP"], variant="c_term" if n == 1 else "n_term")
        return Part(nc["tp"], found[0], found[1], False, "targeting peptide (toolkit part)", found[2], found[3])
    if kind == "linker":
        found = resolve_insert("linker", cfg["id"], site, n, "LINK" + cfg["id"], cfg["bp"])
        return Part(cfg["label"], found[0], found[1], False, "linker (toolkit part)", found[2], found[3])
    if kind == "marker":
        found = resolve_insert("marker", cfg["id"], site, n, "MARK" + cfg["id"], cfg["bp"])
        return Part(cfg["label"], found[0], found[1], False, "surface marker (toolkit part)", found[2], found[3])
    if kind == "intein":
        found = resolve_insert("intein", cfg["id"], site, n, "INT" + cfg["id"], cfg["bp"])
        return Part(cfg["label"], found[0], found[1], False, "intein (toolkit part)", found[2], found[3])
    found = resolve_insert("ncs", "ncs", site, n, "NCS", 30, ncs_role="stop" if kind == "ncsstop" else "plain")
    what = "NCS spacer with stop codon (toolkit part)" if kind == "ncsstop" else "NCS spacer (toolkit part)"
    return Part("NCS", found[0], found[1], False, what, found[2], found[3])


def _middle_parts(nc: dict, cargo_label: str, cargo_antisense: str) -> tuple:
    """(Shell, Cargo) als Teile von Type 0.3. Eine eigene Shell und ein eigenes Cargo sind Nutzereingaben; stammt das Cargo
    unveraendert aus der Cargo-Bibliothek, ist es ein Toolkit-Teil mit Lagerstatus. Die Cargo-Sequenz wird erst spaeter
    (als Antisense) eingesetzt."""
    if nc.get("custom"):
        shell = Part(nc["shell"], nc["seq"], True, True, "your own nanocompartment shell", None, None)
    else:
        found = resolve_insert("shell", nc["shell"], "nc_site", 3, "SHELL" + nc["shell"], nc["shellBp"])
        shell = Part(nc["shell"], found[0], found[1], False, "nanocompartment shell (toolkit part)", found[2], found[3])
    preset = find_library_cargo(reverse_complement(cargo_antisense))
    cargo = Part(cargo_label, None, True, preset is None, "cargo gene of interest" if preset is None else "cargo (toolkit part)",
                 preset.get("on_stock") if preset else None, preset)
    return shell, cargo


def _mark_stop(built: dict, seq: str, module: str) -> None:
    """NCS mit Stopcodon: das Stopcodon im Leseraster als Eintrag in `built["stops"]` markieren."""
    sense = reverse_complement(seq) if module == "cargo" else seq
    off = first_stop_offset(sense)
    if off is None:
        return
    ia, ib = location_span(built["insert"]["location"])
    a = ia + off if module == "nc" else ib - off - 2
    built["stops"].append({"location": f"{a}..{a + 2}", "note": f"stop codon {sense[off:off + 3]} in the reading frame of the ORF"})


def _construct_features(shown: dict, part: Part, n: int, adapter_id: str, orientation: str, codon: dict | None) -> list:
    """Annotationen des Konstrukts (so wie es angezeigt wird): BbsI-Stellen, Overhangs, Frame-Spacer, Stopcodon und das Insert."""
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
    """(Primer, Oligo-Paar) eines Teils. Primer gibt es nur fuer eigene Sequenzen (die man in die Toolbox einbauen will) und nur,
    wenn sie lang genug fuer PCR sind; Toolkit-Teile bestellt man als DNA/Oligos oder fragt das Plasmid beim KIT an. Ein
    Oligo-Paar bekommt jedes Teil mit echter Sequenz unter MIN_PCR_INSERT_BP, egal ob eigene Eingabe oder Toolkit-Teil.
    Die Bindestellen der Primer kommen als Features zu `features` dazu."""
    if not part.is_real:
        primers = {"possible": False, "reason": "No real sequence in the parts database yet; primers can only be designed for a real sequence."}
    elif not part.is_user:
        primers = {"possible": False, "reason": "Toolbox part: request the plasmid from the KIT (igem@blt.kit.edu) or order it as DNA; "
                                                 "primers are only designed for your own sequences."}
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


def _build_construct(part: Part, module: str, n: int, codon: dict | None, backbone: dict | None, cargo_antisense: str) -> tuple:
    """Das Level-0-Konstrukt von Type 0.`n` des Moduls `module` und das BsaI-Fragment dieses Teils fuer Level 1.
    Cargo-Modul-Teile liegen auf dem Antisense-Strang und werden als Reverse Complement eingesetzt (das Cargo ist bereits
    reverse-komplementiert); angezeigt wird die Cargo Site um 180 Grad gedreht, damit das Cargo in seiner eigenen
    Leserichtung steht (5' links -> 3' rechts)."""
    antisense = module == "cargo"
    seq = part.seq
    if antisense:
        seq = cargo_antisense if n == 3 else reverse_complement(seq)
    adapter_id = adapter_id_for(module, n)
    built = attach_adapter(adapter_id, seq)      # Top-Strand des Level-0-Plasmids, 5' links -> 3' rechts
    built["stops"] = []
    if "stop codon" in part.what:
        _mark_stop(built, seq, module)
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
        "primers": primers, "oligos": oligos, "onStock": None if part.is_user else part.on_stock,
        "codon": codon if part.is_user else None,
        "plasmid_source": {"id": part.source["id"], "name": part.source["label"]} if part.source and not part.is_user else None,
        "stopCodon": "stop codon" in part.what, "stopLocation": shown["stops"][0]["location"] if shown["stops"] else None,
        "genbank": format_genbank_record(record_name, shown["sequence"], features, False,
                                         _definition(part.label, adapter_id, antisense, part.is_real)),
        "plasmid": plasmid,
    }
    return construct, fragment


def build_level0_constructs(nc: dict, cargo_label: str, cargo_antisense: str, cargo_slots: dict, nc_slots: dict,
                            fragments: list | None = None, cargo_codon: dict | None = None) -> list:
    """Das Level-0-Konstrukt jedes der zehn Module (Cargo Site + NC Site, Type 0.1-0.5): die Teilsequenz im
    Overhang-Adapter ihres Type-Slots (attach_adapter) und, wenn das Level-0-Backbone in der Datenbank liegt,
    das daraus per BbsI klonierte Plasmid (clone_into_level0_backbone), jeweils mit fertigem GenBank-Text.

    `isUser` = vom Nutzer eingegeben (Cargo, eigene Shell/Teile), sonst Toolkit-Teil; `isReal` = echte
    Sequenz (Nutzereingabe oder Parts-Datenbank) statt deterministischem Platzhalter. Die BsaI-Fragmente aller Teile
    (fuer die Level-1-Assemblierung) kommen, wenn `fragments` uebergeben wird, dort hinein."""
    shell, cargo = _middle_parts(nc, cargo_label, cargo_antisense)
    backbone = next(iter(load_parts()["level0_backbones"]), None)
    if backbone and not backbone.get("sequence"):
        backbone = None

    constructs = []
    for module, slots, middle in (("cargo", cargo_slots, cargo), ("nc", nc_slots, shell)):
        site = "cargo_site" if module == "cargo" else "nc_site"
        for n in (1, 2, 3, 4, 5):
            part = middle if n == 3 else _toolkit_part(slots[n], nc, site, n)
            codon = (cargo_codon if module == "cargo" else nc.get("codon")) if n == 3 else slots[n].get("codon")
            construct, fragment = _build_construct(part, module, n, codon, backbone, cargo_antisense)
            constructs.append(construct)
            if fragments is not None:
                fragments.append(fragment)
    return constructs
