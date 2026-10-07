"""Belegung der vier Module neben dem Mittelteil (Type 0.1, 0.2, 0.4, 0.5) und der Aufbau der Modul-Teile fuer die Anzeige."""

from __future__ import annotations

from .data import NOMINAL_BP, find_intein, find_linker, find_surface_marker
from .sequence import validate_cargo


CUSTOM_NC_ID = "custom"


def build_custom_nanocompartment(custom) -> dict:
    """Eigene Shell-CDS des Nutzers als Nanocompartment-Eintrag.

    Die Sequenz laeuft durch dieselbe Pruefung wie das Cargo (Laenge, kein
    Stopcodon am Ende, Leseraster). Eine eigene Shell bringt kein Targeting-Peptid
    mit (tp = None); im Cargo-Modul geht dann nur noch eine eigene Sequenz.
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
# Teile aus der Bibliothek, die ein Slot aufnehmen kann: Art -> (Suchfunktion, Name fuer die Fehlermeldung)
LIBRARY_PARTS = {"linker": (find_linker, "linker"), "marker": (find_surface_marker, "surface marker"),
                 "intein": (find_intein, "intein")}


def resolve_slots(raw, module: str = "nc") -> dict:
    """Belegung der vier Slots neben dem Mittelteil (Type 0.1, 0.2, 0.4, 0.5).

    ``module`` ist "nc" (Mittelteil = Shell, ORF von Type 0.1 nach 0.5) oder "cargo"
    (Mittelteil = Cargo, ORF laeuft von Type 0.5 nach 0.1, weil das Cargo-Modul auf dem
    Antisense-Strang sitzt). Jeder Slot ist ein NCS-Spacer, ein NCS mit Stopcodon, ein
    Linker, ein Oberflaechen-Marker, im Cargo-Modul ausserdem das Targeting-Peptid, oder
    eine eigene Sequenz. Eigene Sequenzen laufen durch dieselbe Pruefung wie das Cargo.
    Fehlende Slots bleiben NCS.
    """
    raw = raw if isinstance(raw, dict) else {}
    slots = {}
    for n in NC_SLOTS:
        cfg = raw.get(str(n)) or raw.get(n) or {}
        kind = cfg.get("kind") or "ncs"
        if kind in ("ncs", "ncsstop"):
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

    # Slots hinter dem Mittelteil, in ORF-Richtung: Shell -> 4, 5; Cargo (Antisense) -> 2, 1.
    behind = (4, 5) if module == "nc" else (2, 1)
    part_name = "shell" if module == "nc" else "cargo"

    # NCS mit Stopcodon: nur hinter dem Mittelteil, hoechstens einmal, und danach darf nichts
    # mehr uebersetzt werden.
    stops = [n for n in NC_SLOTS if slots[n]["kind"] == "ncsstop"]
    for n in stops:
        if n not in behind:
            raise ValueError(
                f"Type 0.{n}: an NCS with stop codon can only sit behind the {part_name} (Type 0.{behind[0]} or 0.{behind[1]})."
            )
    if len(stops) > 1:
        raise ValueError("Only one NCS can carry the stop codon.")
    if slots[behind[0]]["kind"] == "ncsstop" and slots[behind[1]]["kind"] != "ncs":
        raise ValueError(f"Type 0.{behind[1]}: nothing can follow the stop codon in Type 0.{behind[0]}.")

    # Ist der aeussere Slot (Type 0.1 bzw. 0.5) belegt, darf der innere (0.2 bzw. 0.4) kein
    # NCS-Spacer sein. Sitzt aussen eine CDS (Marker, TP oder eigene Sequenz), muss innen ein
    # Linker sitzen — ein zweiter Marker reicht dort nicht.
    for outer, inner in ((1, 2), (5, 4)):
        if slots[outer]["kind"] not in ("ncs", "ncsstop") and slots[inner]["kind"] == "ncs":
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
    if kind == "ncsstop":
        return {"role": "ncs", "label": "NCS", "kind": "ncs", "note": "Spacer · stop codon", "bp": NOMINAL_BP["NCS"], "stop": True}
    return {"role": "ncs", "label": "NCS", "kind": "ncs", "note": "Spacer", "bp": NOMINAL_BP["NCS"]}


def _module_layout(slots: dict, middle: dict, tp_label: str = "TP") -> list:
    """Die fuenf Teile eines Moduls in Typ-Reihenfolge. Das Stopcodon traegt nur ein vom Nutzer
    ausdruecklich gewaehlter "NCS mit Stopcodon" — es wird nicht automatisch gesetzt."""
    parts = {n: _slot_part(n, slots[n], tp_label) for n in NC_SLOTS}
    return [parts[1], parts[2], middle, parts[4], parts[5]]


def level0_part(slot: int, spec: dict) -> dict:
    # Funktion zur Erstellung eines Level-0-Moduls, eine Art Steckbrief.
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
        # Traegt dieser Slot das Stopcodon? Es sitzt immer am 3'-Ende des ORFs,
        # also am C-Terminus des Fusionsproteins. Welcher Slot das ist, haengt
        # an der Fusionsrichtung bzw. am Display-Terminus.
        "stop": spec.get("stop", False),
    }


def build_modules(nc: dict, cargo_label: str, cargo_bp: int, cargo_slots: dict, nc_slots: dict):
    # Ein Modul besteht aus fuenf Level-0-Teilen. Hier werden Cargo- und NC-Modul aufgebaut.
    cg = {"role": "cargo", "label": cargo_label, "kind": "t3", "note": "Cargo", "bp": cargo_bp, "isCargo": True}
    # Cargo-Modul (Antisense): der ORF laeuft von Type 0.5 nach 0.1.
    cargo_layout = _module_layout(cargo_slots, cg, tp_label=nc["tp"])
    cargo_module = [level0_part(index + 1, spec) for index, spec in enumerate(cargo_layout)]

    shell = {"role": "shell", "label": nc["shell"], "kind": "shell", "note": "Shell", "bp": nc["shellBp"],
             "isNew": bool(nc.get("custom"))}
    # NC-Modul (Sense): der ORF laeuft von Type 0.1 nach 0.5.
    nc_layout = _module_layout(nc_slots, shell)
    nc_module = [level0_part(index + 1, spec) for index, spec in enumerate(nc_layout)]
    return cargo_module, nc_module


def slot_summary(slots: dict) -> list:
    return [
        {"slot": n, **{k: v for k, v in slots[n].items() if k not in ("seq", "validation")},
         **({"sequence": slots[n]["seq"], "isNew": True} if slots[n]["kind"] == "custom" else {})}
        for n in NC_SLOTS
    ]
