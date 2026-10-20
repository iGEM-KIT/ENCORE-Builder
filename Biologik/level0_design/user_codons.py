"""Codon optimization of the sequences entered by the user, within the design: adapter context, summary, GenBank note."""

from __future__ import annotations

from .adapters import adapter_contexts, adapter_id_for
from .codon import optimize_cds, remove_forbidden_sites
from .data import STOP_CODONS
from .parts_db import find_library_cargo
from .slots import orf_slots


def orf_flags(slots: dict, module: str) -> dict:
    """{slot: (start, stop)}: which coding part of a module gets the start codon (first in reading direction) and which the stop codon
    (last). Same rule as in constructs._orf_flags; here it is needed before the construct is built."""
    coding = orf_slots(slots, module)
    return {n: (n == coding[0], n == coding[-1]) for n in coding}


def _with_start_stop(lefts: list, rights: list, start: bool, stop: bool) -> tuple:
    """The start codon ATG (in front) and the stop codon TAA (behind) are added to a part later. They belong to the neighbour
    context of the optimization, so that no restriction site arises across them (for example ATG + AATTC gives the EcoRI site GAATTC)."""
    if start:
        lefts = [left + "ATG" for left in lefts]
    if stop:
        rights = ["TAA" + right for right in rights]
    return lefts, rights


def codon_optimize_part(sequence: str, module: str, slot: int, protein: bool = False, start: bool = False, stop: bool = False) -> dict:
    """Codon optimization (S. cerevisiae, without BsaI, BbsI, SapI, EcoRI, XbaI, SpeI, PstI and NotI sites) of a sense sequence entered by the user that is built into `module`
    ("cargo"/"nc") at Type 0.<slot>. See codon.optimize_cds. With `protein=True`, `sequence` is an amino acid sequence.
    `start`/`stop`: the part is the first/last coding part of its ORF and gets the start/stop codon of the Builder; an ATG or a stop
    codon that the sequence already carries is not added again, so it does not count."""
    seq = (sequence or "").upper()
    add_start = start and not seq.startswith("M" if protein else "ATG")
    add_stop = stop and not (seq.endswith("*") if protein else seq[-3:] in STOP_CODONS)
    lefts, rights = _with_start_stop(*adapter_contexts(adapter_id_for(module, slot), module == "cargo", slot), add_start, add_stop)
    return optimize_cds(sequence, lefts, rights, protein)


def optimize_toolkit_part(sequence: str, module: str, slot: int, start: bool = False, stop: bool = False) -> tuple:
    """Codon optimization of a part of the toolKIT (optional, see the design option "optimizeToolkit"): the same method and the same
    forbidden sites as for the own sequences (S. cerevisiae, RFC 10 and RFC 1000 sites, BsaI, BbsI). Returns (sequence, summary)."""
    lefts, rights = _with_start_stop(*adapter_contexts(adapter_id_for(module, slot), module == "cargo", slot), start, stop)
    result = optimize_cds(sequence, lefts, rights)          # toolKIT parts are stored bare: start and stop codon are always added
    return result["sequence"], codon_summary(result)


def fix_toolkit_sites(sequence: str, module: str, slot: int) -> tuple:
    """For toolKIT parts that are not coding for a protein of their own (the NCS spacers): only a forbidden site is removed, with as few
    synonymous codon changes as possible; without a site the sequence stays as it is. Returns (sequence, summary)."""
    lefts, rights = adapter_contexts(adapter_id_for(module, slot), module == "cargo", slot)
    result = remove_forbidden_sites(sequence, lefts, rights)
    return result["sequence"], codon_summary(result)


def codon_summary(result: dict) -> dict:
    """What the design response and the GenBank notes need from an optimization (without the sequences)."""
    return {"status": result["status"], "fromProtein": result["fromProtein"], "optimized": result["optimized"],
            "reason": result.get("reason"), "changed": result["changed"], "codons": result["codons"],
            "caiBefore": result["caiBefore"], "caiAfter": result["caiAfter"],
            "gcBefore": result["gcBefore"], "gcAfter": result["gcAfter"],
            "sitesRemoved": [f"{h['enzyme']} ({h['site']})" for h in result["forbiddenBefore"]],
            "sitesLeft": [f"{h['enzyme']} ({h['site']})" for h in result["forbiddenAfter"]], "siteFix": bool(result.get("siteFix"))}


def codon_note(summary: dict | None) -> str:
    if not summary:
        return ""
    if summary["status"] != "optimized":
        return f"Codon optimization: {summary['reason']}"
    if summary.get("siteFix"):
        return (f"Restriction site(s) removed with {summary['changed']} synonymous codon change(s), the rest is as in the toolKIT: "
                f"{', '.join(dict.fromkeys(summary['sitesRemoved']))}")
    if summary.get("fromProtein"):
        return (f"Back-translated from the amino acid sequence with S. cerevisiae codon usage: {summary['codons']} codons, "
                f"CAI {summary['caiAfter']}, GC {summary['gcAfter']}%; no restriction sites to avoid")
    removed = (f"; removed {len(summary['sitesRemoved'])} restriction site(s) to avoid" if summary["sitesRemoved"] else "; no restriction sites to avoid")
    return (f"Codon-optimized for S. cerevisiae: {summary['changed']}/{summary['codons']} codons changed, "
            f"CAI {summary['caiBefore']}->{summary['caiAfter']}, GC {summary['gcBefore']}->{summary['gcAfter']}%{removed}")


def optimize_user_sequences(cargo: dict, cargo_label: str, nc: dict, cargo_slots: dict, nc_slots: dict) -> tuple:
    """Codon-optimizes every sequence entered by the user (cargo, own shell, own parts in the slots) for S. cerevisiae;
    the protein stays the same and none of the restriction sites in codon.FORBIDDEN_SITES is created. A cargo from the library is a toolkit part and stays as it is.
    The sequences in `cargo`, `nc` and the slots are replaced and get their summary under "codon".
    Returns (report for the response, summary of the cargo or None)."""
    report = []

    flags = {"cargo": orf_flags(cargo_slots, "cargo"), "nc": orf_flags(nc_slots, "nc")}

    def optimize(role: str, label: str, module: str, slot: int, sequence: str, protein: bool) -> tuple:
        start, stop = flags[module].get(slot, (False, False))
        result = codon_optimize_part(sequence, module, slot, protein, start, stop)
        summary = codon_summary(result)
        report.append({"role": role, "label": label, "module": module, "slot": slot, **summary})
        return result["sequence"], summary

    cargo_codon = None
    if cargo["isProtein"] or not find_library_cargo(cargo["clean"]):
        cargo["clean"], cargo_codon = optimize("cargo", cargo_label, "cargo", 3, cargo["clean"], cargo["isProtein"])
    if nc.get("custom"):
        nc["seq"], nc["codon"] = optimize("shell", nc["label"], "nc", 3, nc["seq"], nc["isProtein"])
    for module, slots in (("cargo", cargo_slots), ("nc", nc_slots)):
        for n, cfg in slots.items():
            if cfg["kind"] == "custom":
                cfg["seq"], cfg["codon"] = optimize("part", cfg["label"], module, n, cfg["seq"], cfg["isProtein"])
    return report, cargo_codon
