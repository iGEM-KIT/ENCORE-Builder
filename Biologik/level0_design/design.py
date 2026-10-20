"""Level 0/1/2 design logic: turns the user's inputs into a complete Golden Gate design including the GenBank export.

The subtasks live in their own modules: slots (assignment of the modules), user_codons (codon optimization of the inputs),
constructs (Level 0 constructs), adapters, cloning, primers, oligos and assembly (Level 1/2)."""

from __future__ import annotations

from .assembly import assemble_level1_module, assemble_level1_promoter, assemble_level2, finish_level1
from .constructs import build_level0_constructs, resolve_seq
from .data import CARGO_L1_FLANK, NOMINAL_BP, TARGETING_PEPTIDES, find_nanocompartment, find_promoter
from .codon import FORBIDDEN_SITES
from .parts_db import find_library_cargo, find_real_sequence, load_parts
from .primers import design_promoter_primers, make_primer_pair, promoter_pcr_genbank
from .sequence import reverse_complement, validate_cargo, validate_promoter
from .slots import CUSTOM_NC_ID, build_custom_nanocompartment, build_modules, resolve_slots, slot_summary
from .user_codons import fix_toolkit_sites, optimize_toolkit_part, optimize_user_sequences, orf_flags


CUSTOM_PROMOTER_ID = "custom"


def _first_backbone(kind: str):
    backbone = next(iter(load_parts()[kind]), None)
    return backbone if backbone and backbone.get("sequence") else None


def build_level1_and_2(fragments: list, promoter_entry: dict, nc: dict):
    """Level 1: cargo module, NC module and promoter, each as an insert (+ plasmid) in the Level 1 backbone (BsaI);
    Level 2: the three inserts in the Level 2 backbone (BbsI). Without a Level 1 backbone in the database: ([], None)."""
    backbone1 = _first_backbone("level1_backbones")
    if not backbone1:
        return [], None
    backbone2 = _first_backbone("level2_backbones")
    by_module = {m: [f for f in fragments if f["module"] == m] for m in ("cargo", "nc")}
    cargo = finish_level1(assemble_level1_module(by_module["cargo"], "Cargo module", "cargo_site", True, "Level1_Cargo"), backbone1)
    ncm = finish_level1(assemble_level1_module(by_module["nc"], "Nanocompartment module", "nc_site", False, "Level1_NC"), backbone1)
    custom = bool(promoter_entry.get("custom"))
    if custom:
        promo_seq, promo_real = promoter_entry["seq"], True
    else:
        promo_seq, promo_real = resolve_seq("promoters", promoter_entry["id"], "PROMO" + promoter_entry["id"], NOMINAL_BP["PROMO"])
    promo = finish_level1(assemble_level1_promoter(promoter_entry["label"], promo_seq, promo_real, "Level1_Promoter", backbone1, is_user=custom), backbone1)
    promo["isUser"] = custom
    if custom:
        # An own promoter is made by PCR: primers with the BsaI site and the Level 1 / Level 2 overhangs, and the PCR product as GenBank.
        promo["primers"] = design_promoter_primers(promo_seq, promoter_entry["label"], promo)
        if promo["primers"]["possible"]:
            promo["primers"]["genbank"] = promoter_pcr_genbank(promo["primers"], promo, promoter_entry["label"])
    level2 = assemble_level2([cargo, promo, ncm], f"ENCORE-{nc['id']}", backbone2)
    return [cargo, promo, ncm], level2


def _resolve_promoter(decisions: dict) -> dict:
    """The promoter of the design: a toolkit promoter of the database, or your own sequence (`promoter` = "custom" and `customPromoter`
    = {label, seq}), which goes through validate_promoter() like every own sequence."""
    if decisions.get("promoter") == CUSTOM_PROMOTER_ID:
        custom = decisions.get("customPromoter") if isinstance(decisions.get("customPromoter"), dict) else {}
        validation = validate_promoter(custom.get("seq", ""))
        if not validation["ok"]:
            raise ValueError("Custom promoter is not usable: " + " ".join(validation["errors"]))
        label = (custom.get("label") or "").strip() or "Custom promoter"
        return {"id": CUSTOM_PROMOTER_ID, "label": label, "desc": "your own sequence", "custom": True, "seq": validation["clean"]}
    return find_promoter(decisions.get("promoter")) or find_promoter("GAL110")


def design_construct(decisions: dict = None):
    # The main flow: a complete design plan is created from the inputs.
    decisions = decisions or {}
    if decisions.get("nanocompartment") == CUSTOM_NC_ID:
        nc = build_custom_nanocompartment(decisions.get("customNanocompartment"))
    else:
        nc = find_nanocompartment(decisions.get("nanocompartment"))
    if not nc:
        raise ValueError(f"Unknown nanocompartment \"{decisions.get('nanocompartment')}\".")

    promoter_entry = _resolve_promoter(decisions)

    cargo = validate_cargo(decisions.get("cargoSeq", ""))
    if not cargo["ok"]:
        raise ValueError("Cargo sequence is not fusion-ready.")

    cargo_label = (decisions.get("cargoLabel") or "").strip() or "Custom cargo"
    cargo_bp = cargo["length"]

    # Assignment of the slots next to cargo and shell (NCS, linker, marker, TP or own sequence).
    cargo_slots = resolve_slots(decisions.get("cargoSlots"), "cargo")
    for cfg in cargo_slots.values():
        if cfg["kind"] == "tp":
            cfg["label"] = nc["tp"]
            cfg["bp"] = next((t["bp"] for t in TARGETING_PEPTIDES if t["id"] == nc["tp"]), NOMINAL_BP["TP"]) if nc.get("tp") else NOMINAL_BP["TP"]
    nc_slots = resolve_slots(decisions.get("ncSlots"), "nc")
    if not nc.get("tp") and any(cfg["kind"] == "tp" for cfg in cargo_slots.values()):
        raise ValueError(f"{'A custom' if nc.get('custom') else 'This'} nanocompartment has no targeting peptide; use your own sequence in that slot.")

    if nc.get("id") != "mvp" and any(cfg["kind"] == "intein" for cfg in (*cargo_slots.values(), *nc_slots.values())):
        raise ValueError("The intein INT is the targeting peptide of the human vault; with this nanocompartment use your own sequence in that slot.")

    codon_report, cargo_codon = optimize_user_sequences(cargo, cargo_label, nc, cargo_slots, nc_slots)
    # Option: the sequences of the toolKIT are optimized again as well (yeast codon usage, no RFC 10 / RFC 1000 sites). A part whose
    # sequence changes is no longer the sequence of its plasmid in the toolKIT: it has no Registry link and is ordered as DNA.
    optimize_toolkit = bool(decisions.get("optimizeToolkit"))
    cargo_reoptimized = False
    if optimize_toolkit and not cargo["isProtein"] and find_library_cargo(cargo["clean"]):
        new_seq, summary = optimize_toolkit_part(cargo["clean"], "cargo", 3, *orf_flags(cargo_slots, "cargo").get(3, (False, False)))
        if new_seq != cargo["clean"]:
            cargo["clean"], cargo_codon, cargo_reoptimized = new_seq, summary, True
    # The cargo sits in pESC (MCS1) on the antisense strand. So the reverse complement is formed right
    # here and only that is used from now on:
    # primers, order sequence and GenBank refer to the antisense strand.
    # The entered (sense) sequence is only kept for validation and display.
    # NOTE on naming: internally (in the code) this value is called "antisense" (gene-related: it is the
    # reverse complement of the entered CDS). In the display (order box, order list) it is
    # called "sense", because pESC itself names this strand that way: the cargo sits on the
    # antisense strand of MCS1 for exactly that reason. Only the word in the display flips, not the value.
    cargo_antisense = reverse_complement(cargo["clean"])

    cargo_module, nc_module = build_modules(nc, cargo_label, cargo_bp, cargo_slots, nc_slots)
    primers = make_primer_pair(cargo_antisense, CARGO_L1_FLANK[0], CARGO_L1_FLANK[1])

    fragments: list = []
    level0_constructs = build_level0_constructs(nc, cargo_label, cargo_antisense, cargo_slots, nc_slots, fragments, cargo_codon,
                                                optimize_toolkit_part if optimize_toolkit else None, cargo_reoptimized,
                                                fix_toolkit_sites if optimize_toolkit else None)
    level1_constructs, level2_construct = build_level1_and_2(fragments, promoter_entry, nc)
    toolkit_optimization = _toolkit_optimization_report(optimize_toolkit, level0_constructs, level2_construct)

    return {
        "nanocompartment": {"id": nc["id"], "label": nc["label"], "T": nc["T"], "dia": nc["dia"], "shell": nc["shell"], "shellBp": nc["shellBp"],
                            "custom": bool(nc.get("custom")),
                            **({"sequence": nc["seq"]} if nc.get("custom") else {})},
        "targetingPeptide": nc["tp"],
        "cargo": {"label": cargo_label, "sequence": cargo["clean"], "sequenceAntisense": cargo_antisense, "bp": cargo_bp},
        "level0": {"cargoModule": cargo_module, "ncModule": nc_module},
        "level2": {"promoter": {"id": promoter_entry["id"], "label": promoter_entry["label"], "isUser": bool(promoter_entry.get("custom")),
                                "bp": len(promoter_entry.get("seq") or find_real_sequence("promoters", promoter_entry["id"]) or "") or NOMINAL_BP["PROMO"]}},
        "cargoSlots": slot_summary(cargo_slots),
        "ncSlots": slot_summary(nc_slots),
        "primers": primers,
        "codonOptimization": codon_report,
        "toolkitOptimization": toolkit_optimization,
        "level0Constructs": level0_constructs,
        "level1Constructs": level1_constructs,
        "level2Construct": level2_construct,
    }


def _forbidden_sites_in(sequence: str) -> list:
    """The forbidden sites (codon.FORBIDDEN_SITES) in a sequence, on either strand, as "EcoRI (GAATTC)"."""
    other = reverse_complement(sequence)
    return [f"{enzyme} ({sites[0]})" for enzyme, sites in FORBIDDEN_SITES.items() if any(s in sequence or s in other for s in sites)]


def _toolkit_optimization_report(enabled: bool, constructs: list, level2: dict | None) -> dict:
    """What the option "optimize the toolKIT sequences again" did: the parts whose sequence changed (with the sites that were removed)
    and the restriction sites that the finished Level 2 insert still contains (they sit in parts that are not optimized, for example
    the promoter, or in your own sequences, which are optimized anyway)."""
    parts = [{"label": c["label"], "type": c["type"], "module": c["module"], "changed": c["codon"]["changed"], "codons": c["codon"]["codons"],
              "caiBefore": c["codon"]["caiBefore"], "caiAfter": c["codon"]["caiAfter"], "sitesRemoved": list(dict.fromkeys(c["codon"]["sitesRemoved"]))}
             for c in constructs if c.get("reoptimized") and c.get("codon")]
    return {"enabled": enabled, "parts": parts,
            "sitesInInsert": _forbidden_sites_in(level2["sequence"]) if level2 and level2.get("sequence") else None}


def build_genbank(design: dict) -> str:
    """Complete GenBank export: the Level 0 constructs of the user inputs (with PCR product/primers), the three Level 1 inserts
    and the finished Level 2 plasmid (with the real annotations of pESC-HIS); see assembly.py."""
    records: list[str] = []

    # Level 0 constructs of the user inputs (cargo, own shell/parts): part sequence in the Type adapter with all annotations
    # (BbsI sites, overhangs, frame spacer, insert), plus the PCR product with the primers where there is one.
    for c in (c for c in design.get("level0Constructs", []) if c["isUser"] or c.get("reoptimized")):
        records.append(c["genbank"])
        if c["primers"]["possible"]:
            records.append(c["primers"]["genbank"])

    # An own promoter: its PCR product with the two primers (BsaI site + Level 1 overhangs).
    for module in design.get("level1Constructs", []):
        if module.get("isUser") and module.get("primers", {}).get("possible"):
            records.append(module["primers"]["genbank"])

    # Level 1 (BsaI) and Level 2 (BbsI): the actual assemblies including overhangs (see assembly.py).
    for module in design.get("level1Constructs", []):
        records.append(module["shown"]["genbank"] if module.get("shown") else module["genbank"])
    level2 = design.get("level2Construct")
    if level2:
        records.append(level2["plasmid"]["genbank"] if level2["plasmid"] else level2["genbank"])

    return "\n\n".join(records)
