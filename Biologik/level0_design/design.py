from __future__ import annotations

"""Level-0-Design-Logik für die Erstellung von Golden-Gate-Modulen in Python."""

from typing import List

from .data import (
    NANOCOMPARTMENTS,
    BSAI_PRIMER_PREFIX,
    CARGO_L1_FLANK,
    LINKERS,
    NOMINAL_BP,
    PROMO_FLANK,
    TYPE_OVERHANGS,
    find_linker,
    find_nanocompartment,
    find_promoter,
    find_surface_marker,
)
# Sequence-py enthält Funktionen für die Verarbeitung von DNA-Sequenzen
# Z.B. zum Bilden von Komplementären DNA-Sequenzen, zur Berechnung der Schmelztemperatur
from .sequence import reverse_complement, validate_cargo, wallace_tm


CUSTOM_NC_ID = "custom"


def build_custom_nanocompartment(custom) -> dict:
    """Eigene Shell-CDS des Nutzers als Nanocompartment-Eintrag.

    Die Sequenz laeuft durch dieselbe Pruefung wie das Cargo (Laenge, kein
    Stopcodon am Ende, Leseraster). Das Targeting-Peptid haengt nicht an der
    Shell, deshalb waehlt der Nutzer eines der vorhandenen.
    """
    custom = custom if isinstance(custom, dict) else {}
    tps = sorted({nc["tp"] for nc in NANOCOMPARTMENTS})
    tp = custom.get("tp") or tps[0]
    if tp not in tps:
        raise ValueError(f"Unknown targeting peptide \"{tp}\".")
    validation = validate_cargo(custom.get("seq", ""), kind="shell")
    if not validation["ok"]:
        raise ValueError("Custom nanocompartment shell is not fusion-ready: " + " ".join(validation["errors"]))
    label = (custom.get("label") or "").strip() or "Custom shell"
    return {
        "id": CUSTOM_NC_ID, "label": label, "T": None, "dia": None, "tp": tp,
        "shell": label, "shellBp": validation["length"], "custom": True,
        "seq": validation["clean"], "validation": validation,
    }


NC_SLOTS = (1, 2, 4, 5)


def resolve_nc_slots(raw) -> dict:
    """Belegung der vier Slots neben der Shell (Type 1, 2, 4, 5).

    Jeder Slot ist ein NCS-Spacer (Standard), ein Linker, ein Oberflaechen-Marker
    (SpyCatcher/SpyTag) oder eine eigene Sequenz. Eigene Sequenzen laufen durch
    dieselbe Pruefung wie das Cargo. Fehlende Slots bleiben NCS.
    """
    raw = raw if isinstance(raw, dict) else {}
    slots = {}
    for n in NC_SLOTS:
        cfg = raw.get(str(n)) or raw.get(n) or {}
        kind = cfg.get("kind") or "ncs"
        if kind == "ncs":
            slots[n] = {"kind": "ncs"}
        elif kind == "ncsstop":
            slots[n] = {"kind": "ncsstop"}
        elif kind == "linker":
            item = find_linker(cfg.get("id"))
            if not item:
                raise ValueError(f"Type 0.{n}: unknown linker \"{cfg.get('id')}\".")
            slots[n] = {"kind": "linker", "id": item["id"], "label": item["label"], "aa": item["aa"], "bp": item["bp"]}
        elif kind == "marker":
            item = find_surface_marker(cfg.get("id"))
            if not item:
                raise ValueError(f"Type 0.{n}: unknown surface marker \"{cfg.get('id')}\".")
            slots[n] = {"kind": "marker", "id": item["id"], "label": item["label"], "aa": item["aa"], "bp": item["bp"]}
        elif kind == "custom":
            validation = validate_cargo(cfg.get("seq", ""), kind="part")
            if not validation["ok"]:
                raise ValueError(f"Type 0.{n}: your sequence is not fusion-ready. " + " ".join(validation["errors"]))
            label = (cfg.get("label") or "").strip() or f"Custom part {n}"
            slots[n] = {"kind": "custom", "label": label, "seq": validation["clean"], "bp": validation["length"],
                        "aa": validation["aa"], "validation": validation}
        else:
            raise ValueError(f"Type 0.{n}: unknown kind \"{kind}\".")

    # NCS mit Stopcodon: nur hinter der Shell (Type 0.4 oder 0.5), hoechstens einmal, und danach
    # darf nichts mehr uebersetzt werden.
    stops = [n for n in NC_SLOTS if slots[n]["kind"] == "ncsstop"]
    for n in stops:
        if n not in (4, 5):
            raise ValueError(f"Type 0.{n}: an NCS with stop codon can only sit behind the shell (Type 0.4 or 0.5).")
    if len(stops) > 1:
        raise ValueError("Only one NCS can carry the stop codon.")
    if slots[4]["kind"] == "ncsstop" and slots[5]["kind"] != "ncs":
        raise ValueError("Type 0.5: nothing can follow the stop codon in Type 0.4.")

    # Ist der aeussere Slot (Type 1 bzw. 5) belegt, darf der innere (Type 2 bzw. 4) kein NCS-Spacer
    # sein. Sitzt aussen eine CDS (Marker oder eigene Sequenz), muss innen ein Linker sitzen —
    # ein zweiter Marker reicht dort nicht.
    for outer, inner in ((1, 2), (5, 4)):
        if slots[outer]["kind"] not in ("ncs", "ncsstop") and slots[inner]["kind"] == "ncs":
            raise ValueError(f"Type 0.{inner}: cannot be an NCS spacer while Type 0.{outer} is in use.")
        if slots[outer]["kind"] in ("marker", "custom") and slots[inner]["kind"] == "marker":
            raise ValueError(
                f"Type 0.{inner}: a linker is required next to the sequence in Type 0.{outer} "
                f"(choose a linker or your own linker sequence, not a marker)."
            )
    return slots


def _slot_part(n: int, cfg: dict) -> dict:
    kind = cfg["kind"]
    if kind == "linker":
        return {"role": "nc-linker", "label": cfg["label"], "kind": "t2", "note": f"{cfg['aa']} aa", "bp": cfg["bp"]}
    if kind == "marker":
        return {"role": "surface-marker", "label": cfg["label"], "kind": "mark",
                "note": f"{cfg['aa']} aa · surface display", "bp": cfg["bp"], "surface": True}
    if kind == "custom":
        return {"role": "custom-part", "label": cfg["label"], "kind": f"t{n}", "note": f"{cfg['bp']} bp · your sequence",
                "bp": cfg["bp"], "isNew": True, "sequence": cfg["seq"]}
    if kind == "ncsstop":
        return {"role": "ncs", "label": "NCS", "kind": "ncs", "note": "Spacer · stop codon", "bp": NOMINAL_BP["NCS"], "stop": True}
    return {"role": "ncs", "label": "NCS", "kind": "ncs", "note": "Spacer", "bp": NOMINAL_BP["NCS"]}


def level0_part(slot: int, spec: dict) -> dict:
    # Funktion zur Erstellung eines Level-0-Moduls, eine Art Steckbrief.
    # TYPE_OVERHANGS enthält die festen Überhänge für jeden Slot eines Level-0-Parts.
    overhang5, overhang3 = TYPE_OVERHANGS[slot]
    return {
        "slot": slot,
        "type": f"Type 0.{slot}",
        "role": spec["role"],
        "label": spec["label"],
        "kind": spec["kind"],
        "note": spec["note"],
        "bp": spec["bp"],
        "overhang5": overhang5,
        "overhang3": overhang3,
        "surface": spec.get("surface", False),
        "isCargo": spec.get("isCargo", False),
        "isNew": spec.get("isNew", False),
        **({"sequence": spec["sequence"]} if spec.get("sequence") else {}),
        # Traegt dieser Slot das Stopcodon? Es sitzt immer am 3'-Ende des ORFs,
        # also am C-Terminus des Fusionsproteins. Welcher Slot das ist, haengt
        # an der Fusionsrichtung bzw. am Display-Terminus.
        "stop": spec.get("stop", False),
    }


def build_modules(nc: dict, link: dict, cargo_label: str, cargo_bp: int, fusion: str, nc_slots: dict = None):
    # Ein Modul besteht aus mehreren Level-0-Teilen. Hier werden die Bausteine für Cargo- und NC-Modul aufgebaut.
    nc_slots = nc_slots or resolve_nc_slots(None)
    tp = {"role": "targeting-peptide", "label": nc["tp"], "kind": "t1", "note": "Targeting peptide", "bp": NOMINAL_BP["TP"]}
    lk = {"role": "linker", "label": link["label"], "kind": "t2", "note": f"{link['aa']} aa", "bp": link["bp"]}
    cg = {"role": "cargo", "label": cargo_label, "kind": "t3", "note": f"{cargo_bp} bp", "bp": cargo_bp, "isCargo": True}

# NCS steht für Spacer Baustein: Kurzes Verbindungsstück, das zwischen die anderen Bausteine gesetzt wird
    def ncs():
        # Eine verschachtelte Funktion ist eine kleine Hilfe-Funktion innerhalb einer anderen Funktion.
        return {"role": "ncs", "label": "NCS", "kind": "ncs", "note": "Spacer", "bp": NOMINAL_BP["NCS"]}

    # Der ORF laeuft von Type 5 nach Type 1. Bei C-terminaler Fusion ist das
    # Targeting-Peptid der C-Terminus und traegt das Stopcodon; bei
    # N-terminaler Fusion sitzt es im NCS direkt hinter dem Cargo.
    if fusion == "C":
        cargo_layout = [{**tp, "stop": True}, lk, cg, ncs(), ncs()]
    else:
        cargo_layout = [ncs(), {**ncs(), "stop": True}, cg, lk, tp]

    # Eine List-Comprehension baut aus einer Liste schnell eine Liste mit verarbeiteten Elementen.
    cargo_module = [level0_part(index + 1, spec) for index, spec in enumerate(cargo_layout)]

    shell = {"role": "shell", "label": nc["shell"], "kind": "shell", "note": f"{nc['shellBp']} bp", "bp": nc["shellBp"],
             "isNew": bool(nc.get("custom"))}

    # NC-Modul (Sense, ORF von Type 1 nach Type 5): frei belegbare Slots 1, 2, 4, 5 um die Shell.
    # Das Stopcodon sitzt am 3'-Ende des ORFs: im letzten belegten Slot hinter der Shell,
    # sonst im ersten NCS direkt hinter der Shell (Type 4). Ist Slot 4 belegt und Slot 5
    # ein NCS, uebernimmt dieser NCS das Stopcodon.
    parts = {n: _slot_part(n, nc_slots[n]) for n in NC_SLOTS}
    if not any(cfg["kind"] == "ncsstop" for cfg in nc_slots.values()):
        after_shell_used = nc_slots[4]["kind"] != "ncs" or nc_slots[5]["kind"] != "ncs"
        stop_slot = 5 if after_shell_used else 4
        parts[stop_slot] = {**parts[stop_slot], "stop": True}
    nc_layout = [parts[1], parts[2], shell, parts[4], parts[5]]

    nc_module = [level0_part(index + 1, spec) for index, spec in enumerate(nc_layout)]
    return cargo_module, nc_module


def _wallace_primer_pair(sequence: str, oh_f: str, oh_r: str):
    """Grobe Abschaetzung ueber die Wallace-Regel (2 °C je A/T, 4 °C je G/C).

    Fallback, wenn primer3 nicht installiert ist oder kein Paar findet. Reicht
    fuer die Vorschau, nicht fuer die Bestellung.
    """
    # Funktionen können Schleifen verwenden, um einen Wert schrittweise zu verbessern
    # len_f und len_r sind die Annealing-Längen der Primer. Sie werden angepasst, damit die Tm-Werte passend sind.
    len_f = 22
    len_r = 22
    balanced = False
    for _ in range(12):
        tm_f = wallace_tm(sequence[:len_f])
        tm_r = wallace_tm(reverse_complement(sequence[-len_r:]))
        if abs(tm_f - tm_r) <= 5:
            balanced = True
            break
        if tm_f > tm_r and len_f > 16:
            len_f -= 1
        elif tm_r > tm_f and len_r > 16:
            len_r -= 1
        else:
            # Abbruch, weil keine sinnvolle Anpassung mehr möglich
            break

    anneal_f = sequence[:len_f]
    anneal_r = reverse_complement(sequence[-len_r:])

    hint = None
    if not balanced:
        hint = (
            "Hinweis: Die automatische Anpassung der Primer-Längen konnte die Schmelztemperaturen nicht auf "
            "weniger als 5°C Differenz bringen. Überprüfe die Primer manuell oder passe die Sequenz/Annealing-Längen an."
        )

    primers = _assemble_primers(anneal_f, anneal_r, oh_f, oh_r, wallace_tm(anneal_f), wallace_tm(anneal_r))
    for primer in primers:
        primer["tmMethod"] = "wallace"
        if hint:
            primer["note"] = hint

    return primers


def _primer3_primer_pair(sequence: str, oh_f: str, oh_r: str):
    """Echte Nearest-Neighbor-Thermodynamik aus ``Biologik.primer_design``.

    Der Import ist bewusst lokal: ``level0_design`` soll ohne primer3 nutzbar
    bleiben, deshalb wird die Abhaengigkeit erst beim Aufruf gezogen.

    Die Dimer-/Hairpin-Bewertung laeuft nur auf dem ANNEALING-Bereich, nicht
    auf dem fertigen Oligo. Grund: ``BSAI_PRIMER_PREFIX`` endet auf einem
    literalen "N", und primer3 lehnt Nicht-ACGT-Basen ab
    ("Sequence contains non-ACGT base 'N'"). Sobald der Spacer auf eine
    konkrete Base festgelegt ist, sollte hier der volle Primer geprueft werden
    (ueber ``ext_fw`` / ``ext_rv`` in ``design_primers``) — der Ueberhang
    veraendert die Sekundaerstruktur messbar.
    """
    from ..primer_design import design_primers

    result = design_primers(sequence=sequence)

    primers = _assemble_primers(
        result["annealFw"],
        result["annealRv"],
        oh_f,
        oh_r,
        round(result["tmFw"], 1),
        round(result["tmRv"], 1),
    )
    for primer in primers:
        primer["tmMethod"] = "primer3-nn"
        primer["q5AnnealingTemp"] = round(result["q5AnnealingTemp"], 1)
        primer["valid"] = result["valid"]
        primer["issues"] = list(result["issues"])

    return primers


def _assemble_primers(anneal_f: str, anneal_r: str, oh_f: str, oh_r: str, tm_f, tm_r):
    """Baut die beiden Primer-Eintraege aus Annealing-Teil + BsaI-Praefix + Overhang.

    Die Overhangs kommen unveraendert von der aufrufenden Stelle (aktuell
    CARGO_L1_FLANK). Sie sind NICHT identisch mit den Extensions in
    ``primer_design/add_extensions.py`` (type0.3 haengt TTCT an, also den
    Type-3-Overhang aus TYPE_OVERHANGS). Welche Variante die reale Toolbox
    beschreibt, ist offen — siehe PROJECT_TODO.txt Abschnitt 1. Hier wird
    bewusst nichts entschieden: die Thermodynamik wurde ausgetauscht, die
    Biologie nicht.
    """
    def build(overhang: str, anneal: str) -> str:
        return f"{BSAI_PRIMER_PREFIX}{overhang}{anneal}"

    return [
        {
            "name": "Cargo_F", "role": "forward", "overhang": oh_f, "anneal": anneal_f,
            "full": build(oh_f, anneal_f), "length": len(build(oh_f, anneal_f)), "tm": tm_f,
        },
        {
            "name": "Cargo_R", "role": "reverse", "overhang": oh_r, "anneal": anneal_r,
            "full": build(oh_r, anneal_r), "length": len(build(oh_r, anneal_r)), "tm": tm_r,
        },
    ]


def make_primer_pair(sequence: str, oh_f: str, oh_r: str, use_primer3: bool = True):
    """Primerpaar fuer das Cargo. Nutzt primer3, faellt sonst auf Wallace zurueck.

    ``use_primer3=False`` erzwingt den Fallback (fuer Tests und fuer eine reine
    Vorschau ohne installiertes primer3).
    """
    if use_primer3:
        try:
            return _primer3_primer_pair(sequence, oh_f, oh_r)
        except ImportError:
            pass          # primer3-py nicht installiert -> Wallace
        except ValueError:
            pass          # kein gueltiges Paar gefunden -> Wallace

    return _wallace_primer_pair(sequence, oh_f, oh_r)


def build_plate_plan(nc: dict, link: dict, cargo_label: str, nc_slots: dict = None):
    # Der 96-Well-Plan sagt, welche Bausteine aus dem Stock-Plate für die Assemblierung benötigt werden.
    nc_slots = nc_slots or resolve_nc_slots(None)
    plan = [
        {"well": "A1", "kind": "t1", "name": nc["tp"], "tip": nc["tp"]},
        {"well": "A2", "kind": "t2", "name": link["label"], "tip": "L"},
        {"well": "A3", "kind": "t3", "name": cargo_label, "tip": "C"},
        {"well": "B1", "kind": "shell", "name": nc["shell"], "tip": "Sh"},
        {"well": "B2", "kind": "promo", "name": "GAL1-10", "tip": "P"},
        {"well": "C1", "kind": "ncs", "name": "NCS", "tip": "N"},
        {"well": "C2", "kind": "ncs", "name": "NCS", "tip": "N"},
        {"well": "C3", "kind": "ncs", "name": "NCS", "tip": "N"},
        {"well": "C4", "kind": "ncs", "name": "NCS", "tip": "N"},
        {"well": "C5", "kind": "ncs", "name": "NCS", "tip": "N"},
        {"well": "C6", "kind": "ncs", "name": "NCS", "tip": "N"},
    ]
    # Eine eigene Shell liegt nicht im Stock-Plate — sie wird neu bestellt.
    plan = [w for w in plan if not (nc.get("custom") and w["kind"] == "shell")]
    # Linker und Marker aus den Slots neben der Shell kommen aus dem Stock, jeweils einmal.
    extras = []
    for n in NC_SLOTS:
        cfg = nc_slots[n]
        if cfg["kind"] in ("linker", "marker") and cfg["label"] not in [e["name"] for e in extras]:
            extras.append({"kind": "t2" if cfg["kind"] == "linker" else "mark", "name": cfg["label"], "tip": "L" if cfg["kind"] == "linker" else "M"})
    for index, extra in enumerate(extras):
        plan.append({"well": f"D{index + 1}", **extra})
    return plan


def build_order_list(nc: dict, link: dict, cargo_module: List[dict], cargo_label: str, cargo_bp: int, cargo_seq: str,
                     nc_slots: dict = None):
    nc_slots = nc_slots or resolve_nc_slots(None)

    # Eine innere Funktion hilft, die Auswahl eines bestimmten Bausteins aus dem Modul zu kapseln.
    def role_type(role: str):
        match = next((part for part in cargo_module if part["role"] == role), None)
        return match["type"] if match else None

    fixed = [
        {"name": f"Targeting peptide {nc['tp']}", "sub": f"{role_type('targeting-peptide') or 'Type 0.1/0.5'} · standard module", "kind": "t1"},
        {"name": f"Linker {link['label']}", "sub": f"{role_type('linker') or 'Type 0.2/0.4'} · standard module", "kind": "t2"},
    ]
    if not nc.get("custom"):
        fixed.append({"name": f"Shell CDS {nc['shell']}", "sub": "Nanocompartment · standard module", "kind": "shell"})
    fixed += [
        {"name": "Promoter GAL1-10", "sub": "bidirectional · standard module", "kind": "promo"},
        {"name": "NCS spacer", "sub": "standard module", "kind": "ncs"},
    ]
    # Linker und Marker im Nanocompartment-Site sind Standardmodule; eigene Sequenzen sind neue Teile.
    new_parts = []
    if nc.get("custom"):
        left, right = TYPE_OVERHANGS[3]
        new_parts.append({
            "name": f"{nc['shell']} ({nc['shellBp']} bp)", "kind": "shell", "slot": 3,
            "sub": "Type 0.3 · your own nanocompartment shell — synthesis/PCR with overhangs",
            "withOverhangs": f"{left}{nc['seq']}{right}", "overhangs": {"left": left, "right": right},
        })
    for n in NC_SLOTS:
        cfg = nc_slots[n]
        if cfg["kind"] == "linker":
            fixed.append({"name": f"Linker {cfg['label']}", "sub": f"Type 0.{n} · nanocompartment site · standard module", "kind": "t2"})
        elif cfg["kind"] == "marker":
            fixed.append({"name": f"Surface marker {cfg['label']}", "sub": f"Type 0.{n} · nanocompartment site · standard module · source once", "kind": f"t{n}"})
        elif cfg["kind"] == "custom":
            left, right = TYPE_OVERHANGS[n]
            new_parts.append({
                "name": f"{cfg['label']} ({cfg['bp']} bp)", "kind": f"t{n}", "slot": n,
                "sub": f"Type 0.{n} · your own part — synthesis/PCR with overhangs",
                "withOverhangs": f"{left}{cfg['seq']}{right}", "overhangs": {"left": left, "right": right},
            })

    return {
        "fixed": fixed,
        "new": {
            "name": f"{cargo_label} ({cargo_bp} bp)",
            "sub": "Type 0.3 · your new cargo (antisense, reverse complement) — synthesis/PCR with overhangs",
            "kind": "t3",
            "cargoWithOverhangs": f"{CARGO_L1_FLANK[0]}{cargo_seq}{CARGO_L1_FLANK[1]}",
            "overhangs": {"left": CARGO_L1_FLANK[0], "right": CARGO_L1_FLANK[1]},
        },
        "newParts": new_parts,
    }


def design_construct(decisions: dict = None):
    # Der Hauptaufbau: Aus den Eingaben wird ein kompletter Design-Plan erzeugt.
    decisions = decisions or {}
    if decisions.get("nanocompartment") == CUSTOM_NC_ID:
        nc = build_custom_nanocompartment(decisions.get("customNanocompartment"))
    else:
        nc = find_nanocompartment(decisions.get("nanocompartment"))
    if not nc:
        raise ValueError(f"Unknown nanocompartment \"{decisions.get('nanocompartment')}\".")

    fusion = "N" if decisions.get("fusion") == "N" else "C"
    link = find_linker(decisions.get("linker")) or LINKERS[0]
    promoter_entry = find_promoter(decisions.get("promoter")) or find_promoter("GAL110")

    cargo = validate_cargo(decisions.get("cargoSeq", ""))
    if not cargo["ok"]:
        raise ValueError("Cargo sequence is not fusion-ready.")

    cargo_label = (decisions.get("cargoLabel") or "").strip() or "Custom cargo"
    cargo_bp = cargo["length"]

    # Belegung der Slots neben der Shell (NCS, Linker, Marker oder eigene Sequenz).
    nc_slots = resolve_nc_slots(decisions.get("ncSlots"))

    # Das Cargo sitzt im pESC (MCS1) auf dem Antisense-Strang. Deshalb wird gleich
    # hier das Reverse Complement gebildet und ab da nur noch damit gearbeitet:
    # Primer, Bestellsequenz und FASTA beziehen sich auf den Antisense-Strang.
    # Die eingegebene (Sense-)Sequenz bleibt nur fuer Validierung und Anzeige.
    cargo_antisense = reverse_complement(cargo["clean"])

    cargo_module, nc_module = build_modules(nc, link, cargo_label, cargo_bp, fusion, nc_slots)
    primers = make_primer_pair(cargo_antisense, CARGO_L1_FLANK[0], CARGO_L1_FLANK[1])

    # Die Cargo-Validierung liefert eigene Warnungen; die Primer-Methode kommt dazu,
    # damit im UI erkennbar ist, ob echte Thermodynamik oder nur eine Schaetzung dahintersteht.
    design_warnings = list(cargo["warnings"])
    if nc.get("custom"):
        design_warnings += [f"Custom shell: {w}" for w in nc["validation"]["warnings"]]
    for n in NC_SLOTS:
        if nc_slots[n]["kind"] == "custom":
            design_warnings += [f"Type 0.{n}: {w}" for w in nc_slots[n]["validation"]["warnings"]]
    if primers and primers[0].get("tmMethod") == "wallace":
        design_warnings.append(
            "primer3 is not available — Tm values are rough Wallace estimates (preview only). "
            "Install primer3-py (see Biologik/requirements.txt) for nearest-neighbor Tm, "
            "dimer/hairpin checks and the Q5 annealing temperature."
        )

    return {
        "input": {"nanocompartment": nc["id"], "fusion": fusion, "linker": link["id"], "promoter": promoter_entry["id"], "cargoLabel": cargo_label,
                  "ncSlots": {str(n): {k: v for k, v in nc_slots[n].items() if k not in ("seq", "validation")} for n in NC_SLOTS}},
        "nanocompartment": {"id": nc["id"], "label": nc["label"], "T": nc["T"], "dia": nc["dia"], "shell": nc["shell"], "shellBp": nc["shellBp"],
                            "custom": bool(nc.get("custom")),
                            **({"sequence": nc["seq"], "validation": nc["validation"]} if nc.get("custom") else {})},
        "targetingPeptide": nc["tp"],
        "linker": {"id": link["id"], "label": link["label"], "aa": link["aa"], "bp": link["bp"]},
        "cargo": {"label": cargo_label, "sequence": cargo["clean"], "sequenceAntisense": cargo_antisense, "bp": cargo_bp, "aa": cargo["aa"], "gc": cargo["gc"], "validation": cargo},
        "fusion": fusion,
        "level0": {"total": len(cargo_module) + len(nc_module), "cargoModule": cargo_module, "ncModule": nc_module},
        "level1": {"cargoModule": {"role": f"{fusion}-terminal cargo module", "enzyme": "BsaI", "flanks": {"left": CARGO_L1_FLANK[0], "right": CARGO_L1_FLANK[1]}, "parts": cargo_module}, "ncModule": nc_module},
        "level2": {"promoter": {"id": promoter_entry["id"], "label": promoter_entry["label"], "kind": "promo", "bp": NOMINAL_BP["PROMO"], "flanks": {"left": PROMO_FLANK[0], "right": PROMO_FLANK[1]}}},
        "ncSlots": [
            {"slot": n, **{k: v for k, v in nc_slots[n].items() if k not in ("seq", "validation")},
             **({"sequence": nc_slots[n]["seq"], "isNew": True} if nc_slots[n]["kind"] == "custom" else {})}
            for n in NC_SLOTS
        ],
        "primers": primers,
        "platePlan": build_plate_plan(nc, link, cargo_label, nc_slots),
        "orderList": build_order_list(nc, link, cargo_module, cargo_label, cargo_bp, cargo_antisense, nc_slots),
        "warnings": design_warnings,
    }


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


def fasta_wrap(sequence: str, width: int = 70) -> str:
    return "\n".join(sequence[index:index + width] for index in range(0, len(sequence), width))


def build_fasta(design: dict) -> str:
    # FASTA ist ein einfaches Format für DNA-Sequenzen. Hier wird eine Export-Datei für die Bausteine gebaut.
    # Eine Funktion kann einen neuen String aus mehreren Teilen zusammensetzen.
    output = []

    def add(header: str, sequence: str):
        output.append(f">{header}\n{fasta_wrap(sequence)}")

    nc = design["nanocompartment"]
    link = design["linker"]
    cargo_sense = design["cargo"]["sequence"]
    cargo_seq = design["cargo"]["sequenceAntisense"]
    cargo_name = design["cargo"]["label"].replace(" ", "-")

    tp_seq = placeholder_seq("TP" + design["targetingPeptide"], 36)
    link_seq = placeholder_seq("LINK" + link["id"], link["bp"])
    shell_seq = nc["sequence"] if nc.get("custom") else placeholder_seq("SHELL" + nc["shell"], nc["shellBp"])
    promo_seq = placeholder_seq("PROMO" + design["level2"]["promoter"]["id"], 600)
    ncs_seq = placeholder_seq("NCS", 30)
    slots = {entry["slot"]: entry for entry in design["ncSlots"]}

    def slot_seq(n: int) -> str:
        entry = slots[n]
        if entry["kind"] == "custom":
            return entry["sequence"]
        if entry["kind"] == "linker":
            return placeholder_seq("LINK" + entry["id"], entry["bp"])
        if entry["kind"] == "marker":
            return placeholder_seq("MARK" + entry["id"], entry["bp"])
        return ncs_seq

    add(f"Targeting-Peptide_{design['targetingPeptide']} [Type0.1/0.5] [PLACEHOLDER]", tp_seq)
    add(f"Linker_{link['id']} [Type0.2/0.4] [PLACEHOLDER]", link_seq)
    add(f"Cargo_{cargo_name} [Type0.3] [REAL INPUT {len(cargo_seq)}bp] [ANTISENSE = reverse complement of the input CDS]", cargo_seq)
    add(f"Cargo_{cargo_name}_input-CDS [sense, reference only] [{len(cargo_sense)}bp]", cargo_sense)
    if nc.get("custom"):
        add(f"Nanocompartment-Shell_{nc['shell'].replace(' ', '-')} [Type0.3] [REAL INPUT {len(shell_seq)}bp]", shell_seq)
        add(f"Nanocompartment-Shell_{nc['shell'].replace(' ', '-')}_with-overhangs [{TYPE_OVERHANGS[3][0]}...{TYPE_OVERHANGS[3][1]}]",
            f"{TYPE_OVERHANGS[3][0]}{shell_seq}{TYPE_OVERHANGS[3][1]}")
    else:
        add(f"Nanocompartment-Shell_{nc['shell']} [PLACEHOLDER]", shell_seq)
    add(f"Promoter_{design['level2']['promoter']['label']} [bidirectional] [PLACEHOLDER]", promo_seq)
    add("NCS-Spacer [PLACEHOLDER]", ncs_seq)
    for n in (1, 2, 4, 5):
        entry = slots[n]
        if entry["kind"] == "linker":
            add(f"Linker_{entry['id']} [Type0.{n}] [nanocompartment site] [PLACEHOLDER {entry['bp']}bp]", slot_seq(n))
        elif entry["kind"] == "marker":
            add(f"Surface-Marker_{entry['label']} [Type0.{n}] [nanocompartment site] [PLACEHOLDER {entry['bp']}bp]", slot_seq(n))
        elif entry["kind"] == "custom":
            label = entry["label"].replace(" ", "-")
            add(f"Custom-Part_{label} [Type0.{n}] [REAL INPUT {entry['bp']}bp]", slot_seq(n))
            add(f"Custom-Part_{label}_with-overhangs [{TYPE_OVERHANGS[n][0]}...{TYPE_OVERHANGS[n][1]}]",
                f"{TYPE_OVERHANGS[n][0]}{slot_seq(n)}{TYPE_OVERHANGS[n][1]}")
    add(f"Cargo_{cargo_name}_with-overhangs [antisense]", f"{CARGO_L1_FLANK[0]}{cargo_seq}{CARGO_L1_FLANK[1]}")

    # Das Cargo-Modul liegt im Level-2-Konstrukt auf dem Antisense-Strang: die Top-Strand-Sequenz
    # ist die Typ-Reihenfolge 1..5, jedes Teil als Reverse Complement (das Cargo ist schon
    # Antisense). Es wird danach NICHT noch einmal umgedreht.
    slot_order = (
        [tp_seq, link_seq, cargo_sense, ncs_seq, ncs_seq] if design["fusion"] == "C"
        else [ncs_seq, ncs_seq, cargo_sense, link_seq, tp_seq]
    )
    cargo_module_seq = "".join(reverse_complement(part) for part in slot_order)
    # NC-Modul (Sense): Slots 1, 2, Shell, 4, 5 in Typ-Reihenfolge.
    nc_module_seq = slot_seq(1) + slot_seq(2) + shell_seq + slot_seq(4) + slot_seq(5)
    add(f"Level1_Cargo-Module_{design['fusion']}-terminal [{design['cargo']['label']}]", cargo_module_seq)
    add("Level1_Nanocompartment-Module [" + nc["shell"] + "]", nc_module_seq)

    level2 = cargo_module_seq + promo_seq + nc_module_seq
    add(f"Level2_pESC-ENCORE-{nc['id']}_COMPLETE [~{len(level2)}bp] [Cargo(rev)<-promoter->NC]", level2)

    banner = "; ENCORE Builder — FASTA export (prototype)\n; Standard modules are PLACEHOLDER sequences; the cargo and any own sequences are real input.\n"
    return banner + "\n".join(output)
