"""Assignment of the four modules next to the central part (Type 0.1, 0.2, 0.4, 0.5) and the construction of the module parts for the display."""

from __future__ import annotations

from .data import NOMINAL_BP, find_intein, find_linker, find_surface_marker
from .sequence import validate_cargo


CUSTOM_NC_ID = "custom"


def build_custom_nanocompartment(custom) -> dict:
    """Own shell CDS of the user as a nanocompartment entry.

        The sequence goes through the same check as the cargo (length, no
        stop codon at the end, reading frame). An own shell brings no targeting peptide
        (tp = None); in the cargo module only an own sequence is possible then.

    """
    custom = custom if isinstance(custom, dict) else {}
    validation = validate_cargo(custom.get("seq", ""), kind="shell")
    if not validation["ok"]:
        raise ValueError("Custom nanocompartment shell is not fusion-ready: " + " ".join(validation["errors"]))
    label = (custom.get("label") or "").strip() or "Custom shell"
    return {
        "id": CUSTOM_NC_ID, "label": label, "T": None, "dia": None, "tp": None,
        "shell": label, "shellBp": validation["length"], "custom": True,
        "seq": validation["clean"], "isProtein": validation["isProtein"], "validation": validation,
    }


NC_SLOTS = (1, 2, 4, 5)
# Parts from the library that a slot can take: kind -> (search function, name for the error message)
LIBRARY_PARTS = {"linker": (find_linker, "linker"), "marker": (find_surface_marker, "surface marker"),
                 "intein": (find_intein, "intein")}


def resolve_slots(raw, module: str = "nc") -> dict:
    """Assignment of the four slots next to the central part (Type 0.1, 0.2, 0.4, 0.5).

        ``module`` is "nc" (central part = shell, ORF from Type 0.1 to 0.5) or "cargo"
        (central part = cargo, ORF runs from Type 0.5 to 0.1, because the cargo module sits on the
        antisense strand). Every slot is an NCS spacer, a
        linker, a surface marker, in the cargo module also the targeting peptide, or
        an own sequence. Own sequences go through the same check as the cargo.
        Missing slots stay NCS.

    """
    raw = raw if isinstance(raw, dict) else {}
    slots = {}
    for n in NC_SLOTS:
        cfg = raw.get(str(n)) or raw.get(n) or {}
        kind = cfg.get("kind") or "ncs"
        if kind == "ncs":
            slots[n] = {"kind": kind}
        elif kind == "tp":
            if module != "cargo":
                raise ValueError(f"Type 0.{n}: the targeting peptide belongs to the cargo module.")
            if n not in (1, 5):
                raise ValueError(f"Type 0.{n}: the targeting peptide can only sit in Type 0.1 or 0.5.")
            slots[n] = {"kind": "tp"}
        elif kind in LIBRARY_PARTS:
            find, noun = LIBRARY_PARTS[kind]
            item = find(cfg.get("id"))
            if not item:
                raise ValueError(f"Type 0.{n}: unknown {noun} \"{cfg.get('id')}\".")
            slots[n] = {"kind": kind, "id": item["id"], "label": item["label"], "aa": item["aa"], "bp": item["bp"]}
        elif kind == "custom":
            validation = validate_cargo(cfg.get("seq", ""), kind="part")
            if not validation["ok"]:
                raise ValueError(f"Type 0.{n}: your sequence is not fusion-ready. " + " ".join(validation["errors"]))
            label = (cfg.get("label") or "").strip() or f"Custom part {n}"
            slots[n] = {"kind": "custom", "label": label, "seq": validation["clean"], "bp": validation["length"],
                        "aa": validation["aa"], "isProtein": validation["isProtein"], "validation": validation}
        else:
            raise ValueError(f"Type 0.{n}: unknown kind \"{kind}\".")

    if sum(1 for n in NC_SLOTS if slots[n]["kind"] == "tp") > 1:
        raise ValueError("Only one targeting peptide can be used.")

    # If the outer slot (Type 0.1 or 0.5) is used, the inner one (0.2 or 0.4) must not be an
    # NCS spacer. If a CDS (marker, TP or own sequence) sits outside, a
    # linker must sit inside; a second marker is not enough there.
    for outer, inner in ((1, 2), (5, 4)):
        if slots[outer]["kind"] != "ncs" and slots[inner]["kind"] == "ncs":
            raise ValueError(f"Type 0.{inner}: cannot be an NCS spacer while Type 0.{outer} is in use.")
        if slots[outer]["kind"] in ("marker", "tp", "custom", "intein") and slots[inner]["kind"] in ("marker", "intein"):
            raise ValueError(
                f"Type 0.{inner}: a linker is required next to the sequence in Type 0.{outer} "
                f"(choose a linker or your own linker sequence, not a marker)."
            )
    return slots


def _slot_part(n: int, cfg: dict, tp_label: str = "TP") -> dict:
    kind = cfg["kind"]
    if kind == "tp":
        return {"role": "targeting-peptide", "label": tp_label, "kind": f"t{n}", "note": "Targeting peptide", "bp": NOMINAL_BP["TP"]}
    if kind == "linker":
        return {"role": "nc-linker", "label": cfg["label"], "kind": "t2", "note": "Linker", "bp": cfg["bp"]}
    if kind == "marker":
        return {"role": "surface-marker", "label": cfg["label"], "kind": "mark",
                "note": "Surface marker", "bp": cfg["bp"], "surface": True}
    if kind == "intein":
        return {"role": "intein", "label": cfg["label"], "kind": f"t{n}", "note": "Intein", "bp": cfg["bp"]}
    if kind == "custom":
        return {"role": "custom-part", "label": cfg["label"], "kind": f"t{n}", "note": "Your sequence",
                "bp": cfg["bp"], "isNew": True}
    return {"role": "ncs", "label": "NCS", "kind": "ncs", "note": "Spacer", "bp": NOMINAL_BP["NCS"]}


def orf_slots(slots: dict, module: str) -> list:
    """The coding slots of a module in reading direction: NC module Type 0.1 -> 0.5, cargo module (antisense) Type 0.5 -> 0.1.
    The central part (Type 0.3) is always coding; NCS spacers never are. The first one gets the start codon, the last one the stop codon."""
    order = (1, 2, 3, 4, 5) if module == "nc" else (5, 4, 3, 2, 1)
    return [n for n in order if n == 3 or slots[n]["kind"] != "ncs"]


def _module_layout(slots: dict, middle: dict, module: str, tp_label: str = "TP") -> list:
    """The five parts of a module in Type order. The part that ends the ORF (the last coding part in reading direction, marked
    "stop") carries the stop codon, which the builder adds automatically."""
    parts = {n: _slot_part(n, slots[n], tp_label) for n in NC_SLOTS}
    parts[3] = middle
    last = orf_slots(slots, module)[-1]
    parts[last] = {**parts[last], "stop": True}
    return [parts[1], parts[2], parts[3], parts[4], parts[5]]


def level0_part(slot: int, spec: dict) -> dict:
    # Function to create a Level 0 module, a kind of profile.
    return {
        "slot": slot,
        "type": f"Type 0.{slot}",
        "role": spec["role"],
        "label": spec["label"],
        "kind": spec["kind"],
        "note": spec["note"],
        "bp": spec["bp"],
        "surface": spec.get("surface", False),
        "isCargo": spec.get("isCargo", False),
        "isNew": spec.get("isNew", False),
        # Does this slot carry the stop codon? It always sits at the 3' end of the ORF,
        # that is at the C terminus of the fusion protein. Which slot that is depends
        # on the fusion direction or on the display terminus.
        "stop": spec.get("stop", False),
    }


def build_modules(nc: dict, cargo_label: str, cargo_bp: int, cargo_slots: dict, nc_slots: dict):
    # A module consists of five Level 0 parts. The cargo and NC modules are built here.
    cg = {"role": "cargo", "label": cargo_label, "kind": "t3", "note": "Cargo", "bp": cargo_bp, "isCargo": True}
    # Cargo module (antisense): the ORF runs from Type 0.5 to 0.1.
    cargo_layout = _module_layout(cargo_slots, cg, "cargo", tp_label=nc["tp"])
    cargo_module = [level0_part(index + 1, spec) for index, spec in enumerate(cargo_layout)]

    shell = {"role": "shell", "label": nc["shell"], "kind": "shell", "note": "Shell", "bp": nc["shellBp"],
             "isNew": bool(nc.get("custom"))}
    # NC module (sense): the ORF runs from Type 0.1 to 0.5.
    nc_layout = _module_layout(nc_slots, shell, "nc")
    nc_module = [level0_part(index + 1, spec) for index, spec in enumerate(nc_layout)]
    return cargo_module, nc_module


def slot_summary(slots: dict) -> list:
    return [
        {"slot": n, **{k: v for k, v in slots[n].items() if k not in ("seq", "validation")},
         **({"sequence": slots[n]["seq"], "isNew": True} if slots[n]["kind"] == "custom" else {})}
        for n in NC_SLOTS
    ]
