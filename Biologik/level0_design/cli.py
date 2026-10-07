"""JSON stdin/stdout adapter for the Nitro backend.

Aufruf:

    python -m Biologik.level0_design.cli [design|libraries|validate]

Ohne Argument wird ``design`` ausgeführt — so bleibt der ursprüngliche Aufruf
gültig. Die Nutzlast kommt als JSON über stdin, die Antwort geht als JSON nach
stdout und hat immer dieselbe Hülle:

    {"ok": true,  "<feld>": ...}
    {"ok": false, "error": "..."}

Der Exit-Code ist 0 bei Erfolg und 1 im Fehlerfall. Die Gegenstelle sollte
trotzdem ZUERST stdout auswerten, weil dort die eigentliche Fehlermeldung
steht — stderr bleibt im Normalfall leer.
"""

from __future__ import annotations

import json
import sys

from .data import get_libraries
from .design import build_genbank, design_construct
from .mrna_dimer import check_mrna_structure
from .sequence import validate_cargo
from .user_codons import codon_optimize_part, codon_summary


def _read_payload() -> dict:
    """JSON von stdin lesen. Leere Eingabe ist erlaubt und ergibt {}."""
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise TypeError("Expected a JSON object as payload.")
    return payload


def cmd_design(payload: dict) -> dict:
    """Kompletter Golden-Gate-Entwurf aus den drei Entscheidungen."""
    result = design_construct(payload)

    # Wenn der Nutzer GenBank angefordert hat, den Export mit anhängen.
    if payload.get("genbank"):
        result["genbank"] = build_genbank(result)

    return {"design": result}


def cmd_libraries(payload: dict) -> dict:
    """Auswahllisten für die Dropdowns im Frontend."""
    return {"libraries": get_libraries()}


def cmd_validate(payload: dict) -> dict:
    """Jede vom Nutzer eingegebene CDS pruefen — Cargo, eigene Shell oder eigene
    Sequenz in einem Modul-Slot. Eine ungueltige Sequenz ist KEIN Fehler, sondern
    eine gueltige Antwort mit ``ok: false`` im Validierungsobjekt.

    Nur wenn die Sequenz fusionsbereit ist (``ok: True``), kommt zusaetzlich die Vorschau der
    Codon-Optimierung (``codonOptimization``) und der mRNA-Selbststruktur-Check dazu (braucht ViennaRNA, siehe mrna_dimer.py) —
    eine nicht fusionsbereite Sequenz aendert sich ohnehin noch, das Falten waere
    verschwendete Rechenzeit.
    """
    kind = payload.get("kind") if payload.get("kind") in ("shell", "part") else "cargo"
    validation = validate_cargo(payload.get("cargoSeq", ""), kind=kind)
    if validation["ok"]:
        # Jede eingegebene Sequenz wird beim Bauen codon-optimiert (S. cerevisiae, ohne BsaI/BbsI-Stellen). Hier die Vorschau
        # (Kontext: Cargo -> Type 0.3 des Cargo-Moduls, Shell -> Type 0.3 des NC-Moduls, eigenes Teil -> Slot 4 des NC-Moduls);
        # die mRNA-Struktur wird an der optimierten Sequenz geprueft, denn die wird gebaut.
        module, slot = {"cargo": ("cargo", 3), "shell": ("nc", 3)}.get(kind, ("nc", 4))
        optimized = codon_optimize_part(validation["clean"], module, slot, validation["isProtein"])
        validation = {**validation, "codonOptimization": codon_summary(optimized),
                      "mrnaStructure": check_mrna_structure(optimized["sequence"])}
    return {"validation": validation}


COMMANDS = {
    "design": cmd_design,
    "libraries": cmd_libraries,
    "validate": cmd_validate,
}


def main(argv: list | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    command = argv[0] if argv else "design"

    try:
        if command not in COMMANDS:
            raise ValueError(
                f"Unknown command \"{command}\". Expected one of: {', '.join(COMMANDS)}."
            )
        payload = _read_payload()
        result = COMMANDS[command](payload)

    # design_construct wirft ValueError bei ungültiger Eingabe, json.loads bei
    # kaputtem JSON. Beides ist ein Eingabefehler, kein Absturz.
    except (json.JSONDecodeError, TypeError, ValueError) as error:
        json.dump({"ok": False, "error": str(error)}, sys.stdout)
        return 1

    json.dump({"ok": True, **result}, sys.stdout)
    return 0


if __name__ == "__main__":
    # Das Programm starten und den Rückgabewert als Exit-Code weitergeben
    raise SystemExit(main())
