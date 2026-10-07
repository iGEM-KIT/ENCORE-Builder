"""Codon-Optimierung der vom Nutzer eingegebenen Sequenzen im Design: Kontext des Adapters, Zusammenfassung, GenBank-Notiz."""

from __future__ import annotations

from .adapters import adapter_contexts, adapter_id_for
from .codon import optimize_cds
from .parts_db import find_library_cargo


def codon_optimize_part(sequence: str, module: str, slot: int, protein: bool = False) -> dict:
    """Codon-Optimierung (S. cerevisiae, ohne BsaI/BbsI-Stellen) einer vom Nutzer eingegebenen Sense-Sequenz, die in `module`
    ("cargo"/"nc") an Type 0.<slot> eingebaut wird. Siehe codon.optimize_cds. Mit `protein=True` ist `sequence` eine Aminosaeurefolge."""
    lefts, rights = adapter_contexts(adapter_id_for(module, slot), module == "cargo")
    return optimize_cds(sequence, lefts, rights, protein)


def codon_summary(result: dict) -> dict:
    """Was Design-Antwort und GenBank von einer Optimierung brauchen (ohne die Sequenzen)."""
    return {"status": result["status"], "fromProtein": result["fromProtein"], "optimized": result["optimized"],
            "reason": result.get("reason"), "changed": result["changed"], "codons": result["codons"],
            "caiBefore": result["caiBefore"], "caiAfter": result["caiAfter"],
            "gcBefore": result["gcBefore"], "gcAfter": result["gcAfter"],
            "sitesRemoved": [f"{h['enzyme']} ({h['site']})" for h in result["forbiddenBefore"]],
            "sitesLeft": [f"{h['enzyme']} ({h['site']})" for h in result["forbiddenAfter"]]}


def codon_note(summary: dict | None) -> str:
    if not summary:
        return ""
    if summary["status"] != "optimized":
        return f"Codon optimization: {summary['reason']}"
    if summary.get("fromProtein"):
        return (f"Back-translated from the amino acid sequence with S. cerevisiae codon usage: {summary['codons']} codons, "
                f"CAI {summary['caiAfter']}, GC {summary['gcAfter']}%; no BsaI/BbsI sites")
    removed = (f"; removed {len(summary['sitesRemoved'])} BsaI/BbsI site(s)" if summary["sitesRemoved"] else "; no BsaI/BbsI sites")
    return (f"Codon-optimized for S. cerevisiae: {summary['changed']}/{summary['codons']} codons changed, "
            f"CAI {summary['caiBefore']}->{summary['caiAfter']}, GC {summary['gcBefore']}->{summary['gcAfter']}%{removed}")


def optimize_user_sequences(cargo: dict, cargo_label: str, nc: dict, cargo_slots: dict, nc_slots: dict) -> tuple:
    """Codon-optimiert jede vom Nutzer eingegebene Sequenz (Cargo, eigene Shell, eigene Teile in den Slots) fuer S. cerevisiae;
    das Protein bleibt gleich, es entstehen keine BsaI/BbsI-Stellen. Ein Cargo aus der Bibliothek ist ein Toolkit-Teil und bleibt,
    wie es ist. Die Sequenzen in `cargo`, `nc` und den Slots werden ersetzt und bekommen ihre Zusammenfassung unter "codon".
    Gibt (Bericht fuer die Antwort, Zusammenfassung des Cargos oder None) zurueck."""
    report = []

    def optimize(role: str, label: str, module: str, slot: int, sequence: str, protein: bool) -> tuple:
        result = codon_optimize_part(sequence, module, slot, protein)
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
