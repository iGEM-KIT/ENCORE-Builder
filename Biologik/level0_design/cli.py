"""JSON stdin/stdout adapter for the Nitro backend.

Usage:

    python -m Biologik.level0_design.cli [design|libraries|validate|to_dna]

Without an argument ``design`` is run, so the original call stays valid.
The payload comes as JSON on stdin, the answer goes out as JSON on stdout and always has the same envelope:

    {"ok": true,  "<field>": ...}
    {"ok": false, "error": "..."}

The exit code is 0 on success and 1 on failure. The other side should still read stdout FIRST,
because the actual error message is there; stderr normally stays empty.
"""

from __future__ import annotations

import json
import sys

from .codon import back_translate
from .data import get_libraries
from .design import build_genbank, design_construct
from .mrna_dimer import check_mrna_structure, module_mrna
from .sequence import clean_protein, clean_seq, is_protein, validate_cargo
from .user_codons import codon_optimize_part, codon_summary


def _read_payload() -> dict:
    """Read JSON from stdin. Empty input is allowed and gives {}."""
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise TypeError("Expected a JSON object as payload.")
    return payload


def cmd_design(payload: dict) -> dict:
    """Complete Golden Gate design from the three decisions."""
    result = design_construct(payload)

    # If the user asked for GenBank, attach the export.
    if payload.get("genbank"):
        result["genbank"] = build_genbank(result)

    return {"design": result}


def cmd_libraries(payload: dict) -> dict:
    """Selection lists for the dropdowns in the frontend."""
    return {"libraries": get_libraries()}


def cmd_validate(payload: dict) -> dict:
    """Check every CDS entered by the user: cargo, own shell or own
    sequence in a module slot. An invalid sequence is NOT an error but a
    valid answer with ``ok: false`` in the validation object.

    Only if the sequence is fusion ready (``ok: True``) the preview of the codon optimization
    (``codonOptimization``) and the mRNA self structure check are added (needs ViennaRNA, see mrna_dimer.py);
    a sequence that is not fusion ready still changes anyway, so folding it would be a
    waste of computing time.
    """
    kind = payload.get("kind") if payload.get("kind") in ("shell", "part") else "cargo"
    validation = validate_cargo(payload.get("cargoSeq", ""), kind=kind)
    if validation["ok"]:
        # Every entered sequence is codon-optimized when the construct is built (S. cerevisiae, without BsaI/BbsI sites). Here the preview
        # (context: cargo -> Type 0.3 of the cargo module, shell -> Type 0.3 of the NC module, own part -> slot 4 of the NC module);
        # the mRNA structure is checked on the optimized sequence, because that is what gets built.
        module, slot = {"cargo": ("cargo", 3), "shell": ("nc", 3)}.get(kind, ("nc", 4))
        optimized = codon_optimize_part(validation["clean"], module, slot, validation["isProtein"])
        validation = {**validation, "codonOptimization": codon_summary(optimized),
                      "mrnaStructure": check_mrna_structure(optimized["sequence"])}
    return {"validation": validation}


def cmd_mrna(payload: dict) -> dict:
    """mRNA self-fold / self-dimer of the two complete modules (cargo and nanocompartment) of a design: from the first coding part to the
    first stop codon, NCS spacers left out (see mrna_dimer.module_mrna). Takes the same payload as `design`. Separate from `design`, because
    ViennaRNA needs a few seconds for long modules and the design should not wait for it."""
    design = design_construct(payload)
    modules = {c["site"]: c for c in design["level1Constructs"]}
    out = {}
    for key, site in (("cargo", "cargo_site"), ("nc", "nc_site")):
        module = modules[site]
        out[key] = {"label": module["label"], **module_mrna(module.get("shown") or module)}
    return {"mrna": out}


def cmd_to_dna(payload: dict) -> dict:
    """DNA form of every entered sequence (a protein is back-translated with the yeast codon table), e.g. for the
    biosecurity screening, which expects DNA."""
    sequences = payload.get("sequences") or []
    return {"dna": [back_translate(clean_protein(s)) if is_protein(s) else clean_seq(s) for s in sequences]}


COMMANDS = {
    "design": cmd_design,
    "libraries": cmd_libraries,
    "validate": cmd_validate,
    "mrna": cmd_mrna,
    "to_dna": cmd_to_dna,
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

    # design_construct raises ValueError for invalid input, json.loads for
    # broken JSON. Both are input errors, not crashes.
    except (json.JSONDecodeError, TypeError, ValueError) as error:
        json.dump({"ok": False, "error": str(error)}, sys.stdout)
        return 1

    json.dump({"ok": True, **result}, sys.stdout)
    return 0


if __name__ == "__main__":
    # Run the program and pass the return value on as the exit code
    raise SystemExit(main())
