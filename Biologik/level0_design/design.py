"""Level-0/1/2-Design-Logik: aus den Eingaben des Nutzers ein kompletter Golden-Gate-Entwurf samt GenBank-Export.

Die Teilaufgaben liegen in eigenen Modulen: slots (Belegung der Module), user_codons (Codon-Optimierung der Eingaben),
constructs (Level-0-Konstrukte), adapters, cloning, primers, oligos und assembly (Level 1/2)."""

from __future__ import annotations

from .assembly import assemble_level1_module, assemble_level1_promoter, assemble_level2, finish_level1
from .constructs import build_level0_constructs, resolve_seq
from .data import CARGO_L1_FLANK, NOMINAL_BP, find_nanocompartment, find_promoter
from .parts_db import load_parts
from .primers import make_primer_pair
from .sequence import reverse_complement, validate_cargo
from .slots import CUSTOM_NC_ID, build_custom_nanocompartment, build_modules, resolve_slots, slot_summary
from .user_codons import optimize_user_sequences


def _first_backbone(kind: str):
    backbone = next(iter(load_parts()[kind]), None)
    return backbone if backbone and backbone.get("sequence") else None


def build_level1_and_2(fragments: list, promoter_entry: dict, nc: dict):
    """Level 1: Cargo-Modul, NC-Modul und Promotor je als Insert (+ Plasmid) im Level-1-Backbone (BsaI);
    Level 2: die drei Inserts im Level-2-Backbone (BbsI). Ohne Level-1-Backbone in der Datenbank: ([], None)."""
    backbone1 = _first_backbone("level1_backbones")
    if not backbone1:
        return [], None
    backbone2 = _first_backbone("level2_backbones")
    by_module = {m: [f for f in fragments if f["module"] == m] for m in ("cargo", "nc")}
    cargo = finish_level1(assemble_level1_module(by_module["cargo"], "Cargo module", "cargo_site", True, "Level1_Cargo"), backbone1)
    ncm = finish_level1(assemble_level1_module(by_module["nc"], "Nanocompartment module", "nc_site", False, "Level1_NC"), backbone1)
    promo_seq, promo_real = resolve_seq("promoters", promoter_entry["id"], "PROMO" + promoter_entry["id"], NOMINAL_BP["PROMO"])
    promo = finish_level1(assemble_level1_promoter(promoter_entry["label"], promo_seq, promo_real, "Level1_Promoter", backbone1), backbone1)
    level2 = assemble_level2([cargo, promo, ncm], f"ENCORE-{nc['id']}", backbone2)
    return [cargo, promo, ncm], level2


def design_construct(decisions: dict = None):
    # Der Hauptaufbau: Aus den Eingaben wird ein kompletter Design-Plan erzeugt.
    decisions = decisions or {}
    if decisions.get("nanocompartment") == CUSTOM_NC_ID:
        nc = build_custom_nanocompartment(decisions.get("customNanocompartment"))
    else:
        nc = find_nanocompartment(decisions.get("nanocompartment"))
    if not nc:
        raise ValueError(f"Unknown nanocompartment \"{decisions.get('nanocompartment')}\".")

    promoter_entry = find_promoter(decisions.get("promoter")) or find_promoter("GAL110")

    cargo = validate_cargo(decisions.get("cargoSeq", ""))
    if not cargo["ok"]:
        raise ValueError("Cargo sequence is not fusion-ready.")

    cargo_label = (decisions.get("cargoLabel") or "").strip() or "Custom cargo"
    cargo_bp = cargo["length"]

    # Belegung der Slots neben Cargo und Shell (NCS, Linker, Marker, TP oder eigene Sequenz).
    cargo_slots = resolve_slots(decisions.get("cargoSlots"), "cargo")
    for cfg in cargo_slots.values():
        if cfg["kind"] == "tp":
            cfg["label"] = nc["tp"]
            cfg["bp"] = NOMINAL_BP["TP"]
    nc_slots = resolve_slots(decisions.get("ncSlots"), "nc")
    if nc.get("custom") and any(cfg["kind"] == "tp" for cfg in cargo_slots.values()):
        raise ValueError("A custom nanocompartment has no targeting peptide; use your own sequence in that slot.")

    codon_report, cargo_codon = optimize_user_sequences(cargo, cargo_label, nc, cargo_slots, nc_slots)
    # Das Cargo sitzt im pESC (MCS1) auf dem Antisense-Strang. Deshalb wird gleich
    # hier das Reverse Complement gebildet und ab da nur noch damit gearbeitet:
    # Primer, Bestellsequenz und FASTA beziehen sich auf den Antisense-Strang.
    # Die eingegebene (Sense-)Sequenz bleibt nur fuer Validierung und Anzeige.
    # HINWEIS Benennung: intern/im Code heisst dieser Wert "antisense" (Gen-bezogen: er ist das
    # Reverse Complement der eingegebenen CDS). In der Anzeige (Bestellbox, Bestellliste, FASTA)
    # heisst er "sense", weil pESC selbst diesen Strang so nennt — die Cargo sitzt ja gerade deshalb
    # auf dem Antisense-Strang von MCS1. Nur das Wort in der Anzeige dreht sich um, der Wert nicht.
    cargo_antisense = reverse_complement(cargo["clean"])

    cargo_module, nc_module = build_modules(nc, cargo_label, cargo_bp, cargo_slots, nc_slots)
    primers = make_primer_pair(cargo_antisense, CARGO_L1_FLANK[0], CARGO_L1_FLANK[1])

    fragments: list = []
    level0_constructs = build_level0_constructs(nc, cargo_label, cargo_antisense, cargo_slots, nc_slots, fragments, cargo_codon)
    level1_constructs, level2_construct = build_level1_and_2(fragments, promoter_entry, nc)

    return {
        "nanocompartment": {"id": nc["id"], "label": nc["label"], "T": nc["T"], "dia": nc["dia"], "shell": nc["shell"], "shellBp": nc["shellBp"],
                            "custom": bool(nc.get("custom")),
                            **({"sequence": nc["seq"]} if nc.get("custom") else {})},
        "targetingPeptide": nc["tp"],
        "cargo": {"label": cargo_label, "sequence": cargo["clean"], "sequenceAntisense": cargo_antisense, "bp": cargo_bp},
        "level0": {"cargoModule": cargo_module, "ncModule": nc_module},
        "level2": {"promoter": {"id": promoter_entry["id"], "label": promoter_entry["label"], "bp": NOMINAL_BP["PROMO"]}},
        "cargoSlots": slot_summary(cargo_slots),
        "ncSlots": slot_summary(nc_slots),
        "primers": primers,
        "codonOptimization": codon_report,
        "level0Constructs": level0_constructs,
        "level1Constructs": level1_constructs,
        "level2Construct": level2_construct,
    }


def build_genbank(design: dict) -> str:
    """Gesamt-GenBank-Export: die Level-0-Konstrukte der Nutzereingaben (mit PCR-Produkt/Primern), die drei Level-1-Inserts
    und das fertige Level-2-Plasmid (mit den echten Annotationen von pESC-HIS) — siehe assembly.py."""
    records: list[str] = []

    # Level-0-Konstrukte der Nutzereingaben (Cargo, eigene Shell/Teile): Teilsequenz im Type-Adapter mit allen Annotationen
    # (BbsI-Stellen, Overhangs, Frame-Spacer, Insert), plus ggf. das PCR-Produkt mit den Primern.
    for c in (c for c in design.get("level0Constructs", []) if c["isUser"]):
        records.append(c["genbank"])
        if c["primers"]["possible"]:
            records.append(c["primers"]["genbank"])

    # Level 1 (BsaI) und Level 2 (BbsI): die tatsaechlichen Assemblies samt Overhangs (siehe assembly.py).
    for module in design.get("level1Constructs", []):
        records.append(module["shown"]["genbank"] if module.get("shown") else module["genbank"])
    level2 = design.get("level2Construct")
    if level2:
        records.append(level2["plasmid"]["genbank"] if level2["plasmid"] else level2["genbank"])

    return "\n\n".join(records)
