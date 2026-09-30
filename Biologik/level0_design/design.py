from __future__ import annotations

"""Level-0-Design-Logik für die Erstellung von Golden-Gate-Modulen in Python."""

from typing import List

from .data import (
    NANOCOMPARTMENTS,
    BSAI_PRIMER_PREFIX,
    CARGO_L1_FLANK,
    NOMINAL_BP,
    PROMO_FLANK,
    JUNCTION_OVERHANGS,
    TYPE_OVERHANGS,
    find_linker,
    find_nanocompartment,
    find_promoter,
    find_surface_marker,
)
# Sequence-py enthält Funktionen für die Verarbeitung von DNA-Sequenzen
# Z.B. zum Bilden von Komplementären DNA-Sequenzen, zur Berechnung der Schmelztemperatur
from .sequence import reverse_complement, validate_cargo, wallace_tm
from .mrna_dimer import check_mrna_structure
from .parts_db import find_real_sequence, load_parts
from .genbank_writer import format_genbank_record, location_span, shift_location


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
        if kind == "ncs":
            slots[n] = {"kind": "ncs"}
        elif kind == "ncsstop":
            slots[n] = {"kind": "ncsstop"}
        elif kind == "tp":
            if module != "cargo":
                raise ValueError(f"Type 0.{n}: the targeting peptide belongs to the cargo module.")
            if n not in (1, 5):
                raise ValueError(f"Type 0.{n}: the targeting peptide can only sit in Type 0.1 or 0.5.")
            slots[n] = {"kind": "tp"}
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
        if slots[outer]["kind"] in ("marker", "tp", "custom") and slots[inner]["kind"] == "marker":
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


def _layout_with_stop(slots: dict, middle: dict, behind: tuple, tp_label: str = "TP") -> list:
    """Die fuenf Teile eines Moduls in Typ-Reihenfolge, das Stopcodon am 3'-Ende des ORFs.

    Ohne ausdruecklichen NCS mit Stopcodon traegt das Stopcodon der letzte belegte Slot hinter
    dem Mittelteil, sonst der erste NCS direkt dahinter.
    """
    parts = {n: _slot_part(n, slots[n], tp_label) for n in NC_SLOTS}
    if not any(cfg["kind"] == "ncsstop" for cfg in slots.values()):
        used = any(slots[n]["kind"] != "ncs" for n in behind)
        stop_slot = behind[1] if used else behind[0]
        parts[stop_slot] = {**parts[stop_slot], "stop": True}
    return [parts[1], parts[2], middle, parts[4], parts[5]]


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


def build_modules(nc: dict, cargo_label: str, cargo_bp: int, cargo_slots: dict, nc_slots: dict):
    # Ein Modul besteht aus fuenf Level-0-Teilen. Hier werden Cargo- und NC-Modul aufgebaut.
    cg = {"role": "cargo", "label": cargo_label, "kind": "t3", "note": f"{cargo_bp} bp", "bp": cargo_bp, "isCargo": True}
    # Cargo-Modul (Antisense): der ORF laeuft von Type 0.5 nach 0.1, das Stopcodon sitzt links.
    cargo_layout = _layout_with_stop(cargo_slots, cg, behind=(2, 1), tp_label=nc["tp"])
    cargo_module = [level0_part(index + 1, spec) for index, spec in enumerate(cargo_layout)]

    shell = {"role": "shell", "label": nc["shell"], "kind": "shell", "note": f"{nc['shellBp']} bp", "bp": nc["shellBp"],
             "isNew": bool(nc.get("custom"))}
    # NC-Modul (Sense): der ORF laeuft von Type 0.1 nach 0.5, das Stopcodon sitzt rechts.
    nc_layout = _layout_with_stop(nc_slots, shell, behind=(4, 5))
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


def build_plate_plan(nc: dict, cargo_label: str, cargo_slots: dict, nc_slots: dict):
    # Der 96-Well-Plan sagt, welche Bausteine aus dem Stock-Plate für die Assemblierung benötigt werden.
    plan = [
        {"well": "A3", "kind": "t3", "name": cargo_label, "tip": "C"},
        {"well": "B1", "kind": "shell", "name": nc["shell"], "tip": "Sh"},
        {"well": "B2", "kind": "promo", "name": "GAL1-10", "tip": "P"},
    ] + [{"well": f"C{i}", "kind": "ncs", "name": "NCS", "tip": "N"} for i in range(1, 7)]
    # Eine eigene Shell liegt nicht im Stock-Plate — sie wird neu bestellt.
    plan = [w for w in plan if not (nc.get("custom") and w["kind"] == "shell")]
    # TP, Linker und Marker aus den Slots beider Module kommen aus dem Stock, jeweils einmal.
    extras = []
    for slots in (cargo_slots, nc_slots):
        for n in NC_SLOTS:
            cfg = slots[n]
            if cfg["kind"] in ("tp", "linker", "marker"):
                label = nc["tp"] if cfg["kind"] == "tp" else cfg["label"]
                if label not in [e["name"] for e in extras]:
                    extras.append({"kind": {"tp": f"t{n}", "linker": "t2", "marker": "mark"}[cfg["kind"]], "name": label,
                                   "tip": {"tp": "T", "linker": "L", "marker": "M"}[cfg["kind"]]})
    for index, extra in enumerate(extras):
        plan.append({"well": f"D{index + 1}", **extra})
    return plan


def build_order_list(nc: dict, cargo_label: str, cargo_bp: int, cargo_seq: str, cargo_slots: dict, nc_slots: dict):
    fixed = []
    new_parts = []

    def add_slots(slots: dict, module: str):
        # Cargo-Modul liegt auf dem Antisense-Strang: eigene Teile dort als Reverse Complement bestellen.
        antisense = module == "cargo"
        where = "cargo module" if antisense else "nanocompartment site"
        for n in NC_SLOTS:
            cfg = slots[n]
            if cfg["kind"] == "tp":
                fixed.append({"name": f"Targeting peptide {nc['tp']}", "sub": f"Type 0.{n} · {where} · standard module", "kind": f"t{n}"})
            elif cfg["kind"] == "linker":
                fixed.append({"name": f"Linker {cfg['label']}", "sub": f"Type 0.{n} · {where} · standard module", "kind": "t2"})
            elif cfg["kind"] == "marker":
                fixed.append({"name": f"Surface marker {cfg['label']}", "sub": f"Type 0.{n} · {where} · standard module · source once", "kind": f"t{n}"})
            elif cfg["kind"] == "custom":
                seq = reverse_complement(cfg["seq"]) if antisense else cfg["seq"]
                left, right = JUNCTION_OVERHANGS[n - 1], JUNCTION_OVERHANGS[n]
                new_parts.append({
                    "name": f"{cfg['label']} ({cfg['bp']} bp)", "kind": f"t{n}", "slot": n, "module": module,
                    "sub": f"Type 0.{n} · your own part{' (sense, reverse complement)' if antisense else ''} — synthesis/PCR with overhangs",
                    "withOverhangs": f"{left}{seq}{right}", "overhangs": {"left": left, "right": right},
                })

    add_slots(cargo_slots, "cargo")
    if not nc.get("custom"):
        fixed.append({"name": f"Shell CDS {nc['shell']}", "sub": "Nanocompartment · standard module", "kind": "shell"})
    fixed += [
        {"name": "Promoter GAL1-10", "sub": "bidirectional · standard module", "kind": "promo"},
        {"name": "NCS spacer", "sub": "standard module", "kind": "ncs"},
    ]
    add_slots(nc_slots, "nc")
    if nc.get("custom"):
        left, right = JUNCTION_OVERHANGS[2], JUNCTION_OVERHANGS[3]
        new_parts.insert(0, {
            "name": f"{nc['shell']} ({nc['shellBp']} bp)", "kind": "shell", "slot": 3, "module": "nc",
            "sub": "Type 0.3 · your own nanocompartment shell — synthesis/PCR with overhangs",
            "withOverhangs": f"{left}{nc['seq']}{right}", "overhangs": {"left": left, "right": right},
        })

    return {
        "fixed": fixed,
        "new": {
            "name": f"{cargo_label} ({cargo_bp} bp)",
            "sub": "Type 0.3 · your new cargo (sense, reverse complement) — synthesis/PCR with overhangs",
            "kind": "t3",
            "cargoWithOverhangs": f"{CARGO_L1_FLANK[0]}{cargo_seq}{CARGO_L1_FLANK[1]}",
            "overhangs": {"left": CARGO_L1_FLANK[0], "right": CARGO_L1_FLANK[1]},
        },
        "newParts": new_parts,
    }


def _slot_summary(slots: dict) -> list:
    return [
        {"slot": n, **{k: v for k, v in slots[n].items() if k not in ("seq", "validation")},
         **({"sequence": slots[n]["seq"], "isNew": True} if slots[n]["kind"] == "custom" else {})}
        for n in NC_SLOTS
    ]


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
    # Das Targeting-Peptid in Type 0.1 macht die Fusion C-terminal, in Type 0.5 N-terminal.
    fusion = "C" if cargo_slots[1]["kind"] == "tp" else "N" if cargo_slots[5]["kind"] == "tp" else None

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

    # Faltet sich die mRNA der Cargo auf sich selbst (Haarnadel), oder lagern sich zwei Kopien
    # aneinander an (Dimer)? Beides kann ein scannendes Ribosom blockieren. Das ist eine Eigenschaft
    # der mRNA selbst — dafuer zaehlt die Sense-/Kodierrichtung (cargo["clean"]), nicht der
    # Antisense-Strang, mit dem ab hier fuer Primer/Bestellung/FASTA weitergearbeitet wird.
    cargo_mrna = check_mrna_structure(cargo["clean"])

    # Die Cargo-Validierung liefert eigene Warnungen; die Primer-Methode kommt dazu,
    # damit im UI erkennbar ist, ob echte Thermodynamik oder nur eine Schaetzung dahintersteht.
    design_warnings = list(cargo["warnings"])
    if nc.get("custom"):
        design_warnings += [f"Custom shell: {w}" for w in nc["validation"]["warnings"]]
    for label, slots in (("cargo module", cargo_slots), ("nanocompartment site", nc_slots)):
        for n in NC_SLOTS:
            if slots[n]["kind"] == "custom":
                design_warnings += [f"Type 0.{n} ({label}): {w}" for w in slots[n]["validation"]["warnings"]]
    if fusion is None:
        design_warnings.append("No targeting peptide selected — the cargo will not be encapsulated.")
    if cargo_mrna.get("available"):
        for check_name, label in (("selfFold", "self-fold"), ("selfDimer", "self-dimer")):
            check = cargo_mrna[check_name]
            if check["risk"] in ("moderate", "high"):
                design_warnings.append(
                    f"Cargo mRNA {label} risk: {check['risk']} (ΔG = {check['deltaG']} kcal/mol, "
                    f"z = {check['zScore']} vs. {check['shuffles']} shuffled controls) — this may "
                    "keep the mRNA from being translated. See the mRNA structure note for details."
                )
    elif not cargo_mrna.get("reason", "").startswith("Sequence too short"):
        design_warnings.append(f"mRNA structure check: {cargo_mrna.get('reason')}")
    if primers and primers[0].get("tmMethod") == "wallace":
        design_warnings.append(
            "primer3 is not available — Tm values are rough Wallace estimates (preview only). "
            "Install primer3-py (see Biologik/requirements.txt) for nearest-neighbor Tm, "
            "dimer/hairpin checks and the Q5 annealing temperature."
        )

    def public(slots: dict) -> dict:
        return {str(n): {k: v for k, v in slots[n].items() if k not in ("seq", "validation")} for n in NC_SLOTS}

    return {
        "input": {"nanocompartment": nc["id"], "promoter": promoter_entry["id"], "cargoLabel": cargo_label,
                  "cargoSlots": public(cargo_slots), "ncSlots": public(nc_slots)},
        "nanocompartment": {"id": nc["id"], "label": nc["label"], "T": nc["T"], "dia": nc["dia"], "shell": nc["shell"], "shellBp": nc["shellBp"],
                            "custom": bool(nc.get("custom")),
                            **({"sequence": nc["seq"], "validation": nc["validation"]} if nc.get("custom") else {})},
        "targetingPeptide": nc["tp"],
        "cargo": {"label": cargo_label, "sequence": cargo["clean"], "sequenceAntisense": cargo_antisense, "bp": cargo_bp, "aa": cargo["aa"], "gc": cargo["gc"], "validation": cargo,
                  "mrnaStructure": cargo_mrna},
        "fusion": fusion,
        "level0": {"total": len(cargo_module) + len(nc_module), "cargoModule": cargo_module, "ncModule": nc_module},
        "level1": {"cargoModule": {"role": "cargo module", "enzyme": "BsaI", "flanks": {"left": CARGO_L1_FLANK[0], "right": CARGO_L1_FLANK[1]}, "parts": cargo_module}, "ncModule": nc_module},
        "level2": {"promoter": {"id": promoter_entry["id"], "label": promoter_entry["label"], "kind": "promo", "bp": NOMINAL_BP["PROMO"], "flanks": {"left": PROMO_FLANK[0], "right": PROMO_FLANK[1]}}},
        "cargoSlots": _slot_summary(cargo_slots),
        "ncSlots": _slot_summary(nc_slots),
        "primers": primers,
        "platePlan": build_plate_plan(nc, cargo_label, cargo_slots, nc_slots),
        "orderList": build_order_list(nc, cargo_label, cargo_bp, cargo_antisense, cargo_slots, nc_slots),
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


def _feat(ftype: str, location: str, label: str, note: str | None = None, extra: list | None = None) -> dict:
    qualifiers = [("label", label)]
    if note:
        qualifiers.append(("note", note))
    qualifiers.extend(extra or [])
    return {"type": ftype, "location": location, "qualifiers": qualifiers}


def build_genbank(design: dict) -> str:
    """GenBank-Export statt FASTA: dieselben Sequenzen wie zuvor, aber jetzt mit
    echter Feature-Tabelle (Type-Zuordnung, Quelle PLACEHOLDER/PARTS DB/REAL
    INPUT) statt nur einem Kommentar-Header — siehe genbank_writer.py. Der
    Level-2-COMPLETE-Record verwendet, falls vorhanden, das echte importierte
    Backbone (Biologik/level0_design/parts/level2_backbones/) samt seiner
    echten Annotationen (HIS3, AmpR, Origins, ...), nicht nur die reine
    Insert-Sequenz."""
    records: list[str] = []

    def add_record(name: str, sequence: str, features: list[dict] | None = None,
                    circular: bool = False, definition: str = ""):
        records.append(format_genbank_record(name, sequence, features, circular, definition))

    nc = design["nanocompartment"]
    cargo_sense = design["cargo"]["sequence"]
    cargo_seq = design["cargo"]["sequenceAntisense"]
    cargo_name = design["cargo"]["label"].replace(" ", "-")

    shell_seq, shell_is_real = (nc["sequence"], True) if nc.get("custom") else \
        resolve_seq("nanocompartment_shells", nc["shell"], "SHELL" + nc["shell"], nc["shellBp"])
    promo_seq, promo_is_real = resolve_seq(
        "promoters", design["level2"]["promoter"]["id"], "PROMO" + design["level2"]["promoter"]["id"], 600)
    ncs_seq, ncs_is_real = resolve_seq("ncs_spacers", "standard", "NCS", 30)
    tp_seq, tp_is_real = resolve_seq(
        "targeting_peptides", design["targetingPeptide"], "TP" + design["targetingPeptide"], 36)
    cargo_slots = {entry["slot"]: entry for entry in design["cargoSlots"]}
    nc_slots = {entry["slot"]: entry for entry in design["ncSlots"]}

    def slot_seq(entry: dict) -> tuple[str, bool]:
        if entry["kind"] == "custom":
            return entry["sequence"], True
        if entry["kind"] == "tp":
            return tp_seq, tp_is_real
        if entry["kind"] == "linker":
            return resolve_seq("linkers", entry["id"], "LINK" + entry["id"], entry["bp"])
        if entry["kind"] == "marker":
            return resolve_seq("surface_markers", entry["id"], "MARK" + entry["id"], entry["bp"])
        return ncs_seq, ncs_is_real

    def source_note(is_real: bool) -> str:
        return "Source: parts database (real sequence)." if is_real else "Source: deterministic placeholder — no real sequence in the parts database yet."

    def add_slot_records(slots: dict, where: str, antisense: bool):
        for n in (1, 2, 4, 5):
            entry = slots[n]
            tag = f"Type0.{n}"
            seq, is_real = slot_seq(entry)
            if entry["kind"] == "tp":
                add_record(f"Targeting-Peptide_{design['targetingPeptide']}_{tag}",
                           seq, [_feat("CDS", f"1..{len(seq)}", f"TP_{design['targetingPeptide']}",
                                       f"{tag} · {where}. {source_note(is_real)}")])
            elif entry["kind"] == "linker":
                add_record(f"Linker_{entry['id']}_{tag}",
                           seq, [_feat("misc_feature", f"1..{len(seq)}", f"Linker_{entry['id']}",
                                       f"{tag} · {where}. {source_note(is_real)}")])
            elif entry["kind"] == "marker":
                add_record(f"Surface-Marker_{entry['label']}_{tag}",
                           seq, [_feat("CDS", f"1..{len(seq)}", entry["label"],
                                       f"{tag} · {where} · surface display. {source_note(is_real)}")])
            elif entry["kind"] == "custom":
                label = entry["label"].replace(" ", "-")
                seq = reverse_complement(entry["sequence"]) if antisense else entry["sequence"]
                note = " SENSE = reverse complement of the input." if antisense else ""
                add_record(f"Custom-Part_{label}_{tag}", seq,
                           [_feat("CDS", f"1..{len(seq)}", label, f"{tag} · {where} · real user input.{note}")])
                oh_left, oh_right = JUNCTION_OVERHANGS[n - 1], JUNCTION_OVERHANGS[n]
                add_record(f"Custom-Part_{label}_{tag}_with-overhangs",
                           f"{oh_left}{seq}{oh_right}",
                           [_feat("overhang", f"1..{len(oh_left)}", oh_left, "5' Golden Gate junction overhang"),
                            _feat("CDS", f"{len(oh_left) + 1}..{len(oh_left) + len(seq)}", label),
                            _feat("overhang", f"{len(oh_left) + len(seq) + 1}..{len(oh_left) + len(seq) + len(oh_right)}",
                                  oh_right, "3' Golden Gate junction overhang")])

    add_record(f"Cargo_{cargo_name}", cargo_seq,
               [_feat("CDS", f"1..{len(cargo_seq)}", cargo_name,
                      "Type0.3 · real user input · SENSE = reverse complement of the input CDS")])
    add_record(f"Cargo_{cargo_name}_input-CDS", cargo_sense,
               [_feat("CDS", f"1..{len(cargo_sense)}", cargo_name, "Reference only — the input CDS as typed, before reverse-complementing")])
    add_slot_records(cargo_slots, "cargo module", antisense=True)
    if nc.get("custom"):
        name = nc["shell"].replace(" ", "-")
        add_record(f"Nanocompartment-Shell_{name}", shell_seq,
                   [_feat("CDS", f"1..{len(shell_seq)}", name, "Type0.3 · nanocompartment site · real user input")])
        oh_left, oh_right = JUNCTION_OVERHANGS[2], JUNCTION_OVERHANGS[3]
        add_record(f"Nanocompartment-Shell_{name}_with-overhangs", f"{oh_left}{shell_seq}{oh_right}",
                   [_feat("overhang", f"1..{len(oh_left)}", oh_left, "5' Golden Gate junction overhang"),
                    _feat("CDS", f"{len(oh_left) + 1}..{len(oh_left) + len(shell_seq)}", name),
                    _feat("overhang", f"{len(oh_left) + len(shell_seq) + 1}..{len(oh_left) + len(shell_seq) + len(oh_right)}",
                          oh_right, "3' Golden Gate junction overhang")])
    else:
        add_record(f"Nanocompartment-Shell_{nc['shell']}", shell_seq,
                   [_feat("CDS", f"1..{len(shell_seq)}", nc["shell"], f"Type0.3 · nanocompartment site. {source_note(shell_is_real)}")])
    add_record(f"Promoter_{design['level2']['promoter']['label']}", promo_seq,
               [_feat("promoter", f"1..{len(promo_seq)}", design["level2"]["promoter"]["label"],
                      f"Bidirectional. {source_note(promo_is_real)}")])
    add_record("NCS-Spacer", ncs_seq, [_feat("misc_feature", f"1..{len(ncs_seq)}", "NCS spacer", source_note(ncs_is_real))])
    add_slot_records(nc_slots, "nanocompartment site", antisense=False)
    cargo_with_oh = f"{CARGO_L1_FLANK[0]}{cargo_seq}{CARGO_L1_FLANK[1]}"
    add_record(f"Cargo_{cargo_name}_with-overhangs", cargo_with_oh,
               [_feat("overhang", f"1..{len(CARGO_L1_FLANK[0])}", CARGO_L1_FLANK[0]),
                _feat("CDS", f"{len(CARGO_L1_FLANK[0]) + 1}..{len(CARGO_L1_FLANK[0]) + len(cargo_seq)}", cargo_name),
                _feat("overhang", f"{len(CARGO_L1_FLANK[0]) + len(cargo_seq) + 1}..{len(cargo_with_oh)}", CARGO_L1_FLANK[1])])

    # Das Cargo-Modul liegt im Level-2-Konstrukt auf dem Antisense-Strang: die Top-Strand-Sequenz
    # ist die Typ-Reihenfolge 1..5, jedes Teil als Reverse Complement (das Cargo ist schon
    # Antisense). Es wird danach NICHT noch einmal umgedreht.
    cargo_parts = [slot_seq(cargo_slots[1])[0], slot_seq(cargo_slots[2])[0], cargo_sense, slot_seq(cargo_slots[4])[0], slot_seq(cargo_slots[5])[0]]
    cargo_module_seq = "".join(reverse_complement(part) for part in cargo_parts)
    # NC-Modul (Sense): Slots 1, 2, Shell, 4, 5 in Typ-Reihenfolge.
    nc_parts = [slot_seq(nc_slots[1])[0], slot_seq(nc_slots[2])[0], shell_seq, slot_seq(nc_slots[4])[0], slot_seq(nc_slots[5])[0]]
    nc_module_seq = "".join(nc_parts)

    def sub_features(parts: list[str], labels: list[str], antisense: bool) -> list[dict]:
        feats, offset = [], 0
        for part, label in zip(parts, labels):
            start, end = offset + 1, offset + len(part)
            loc = f"complement({start}..{end})" if antisense else f"{start}..{end}"
            feats.append(_feat("misc_feature", loc, label))
            offset += len(part)
        return feats

    # Fuer die Cargo-Modul-Unterfeatures gilt: jedes Type-Segment ist im Record bereits
    # reverse-komplementiert abgelegt (siehe cargo_module_seq oben) — die tatsaechliche
    # 5'->3'-Leserichtung jedes Teils zeigt deshalb von hoher zu niedriger Position, daher
    # complement() in den Sub-Features (spiegelt exakt wider, wie das im Frontend gezeichnet wird).
    cargo_labels = ["Type0.1", "Type0.2", cargo_name, "Type0.4", "Type0.5"]
    nc_labels = ["Type0.1", "Type0.2", nc["shell"], "Type0.4", "Type0.5"]
    add_record(f"Level1_Cargo-Module_{cargo_name}", cargo_module_seq,
               sub_features(cargo_parts, cargo_labels, antisense=True))
    add_record(f"Level1_Nanocompartment-Module_{nc['shell']}", nc_module_seq,
               sub_features(nc_parts, nc_labels, antisense=False))

    level2_seq = cargo_module_seq + promo_seq + nc_module_seq
    insert_labels = cargo_labels + [design["level2"]["promoter"]["label"]] + nc_labels
    insert_parts = cargo_parts + [promo_seq] + nc_parts
    insert_antisense = [True] * 5 + [False] * 6

    backbone = next(iter(load_parts()["level2_backbones"]), None)
    if backbone and backbone.get("sequence"):
        add_record(*_merge_into_backbone(backbone, level2_seq, insert_parts, insert_labels, insert_antisense, nc["id"]))
    else:
        feats = []
        offset = 0
        for part, label, antisense in zip(insert_parts, insert_labels, insert_antisense):
            start, end = offset + 1, offset + len(part)
            loc = f"complement({start}..{end})" if antisense else f"{start}..{end}"
            feats.append(_feat("misc_feature", loc, label))
            offset += len(part)
        add_record(f"Level2_pESC-ENCORE-{nc['id']}_COMPLETE", level2_seq, feats, circular=True,
                   definition="No real Level 2 backbone in the parts database — insert only, not embedded in a destination vector.")

    return "\n\n".join(records)


def _merge_into_backbone(backbone: dict, insert_seq: str, insert_parts: list[str], insert_labels: list[str],
                          insert_antisense: list[bool], nc_id: str) -> tuple[str, str, list[dict], bool, str]:
    """Ersetzt die aktuell im echten Backbone sitzende Stuffer-/Testkassette
    (zwischen den beiden Akzeptor-Overhangs) durch das frisch assemblierte
    Insert und verschiebt alle ECHTEN Backbone-Features hinter dem Stuffer
    entsprechend — die Backbone-Annotationen (Marker, Origins, ...) bleiben so
    an ihrer korrekten Position im neuen, laengeren/kuerzeren Plasmid erhalten.
    Returns (name, sequence, features, circular, definition) fuer add_record()."""
    seq = backbone["sequence"]
    oh5 = backbone["receiver_overhangs"]["5_prime"]
    oh3 = backbone["receiver_overhangs"]["3_prime"]
    stuffer_start = location_span(oh5["location"])[1] + 1   # gleich hinter dem Ende des 5'-Overhangs
    stuffer_end = location_span(oh3["location"])[0] - 1     # gleich vor dem Anfang des 3'-Overhangs
    shift = len(insert_seq) - (stuffer_end - stuffer_start + 1)

    kept_features = []
    for feature in backbone.get("features", []):
        lo, hi = location_span(feature["location"])
        if hi < stuffer_start:
            kept_features.append(feature)
        elif lo > stuffer_end:
            kept_features.append({**feature, "location": shift_location(feature["location"], shift)})
        # sonst: liegt (teilweise) im Stuffer-Bereich -> das ist die ALTE Testkassette, wird verworfen.

    def to_genbank_feature(f: dict) -> dict:
        # /translation weglassen (macht Records unnoetig lang, laesst sich aus der Sequenz ableiten).
        qualifiers = [(key, value) for key, values in f["qualifiers"].items() if key != "translation" for value in values]
        return {"type": f["type"], "location": f["location"], "qualifiers": qualifiers}

    features = [to_genbank_feature(f) for f in kept_features]

    offset = stuffer_start - 1
    for part, label, antisense in zip(insert_parts, insert_labels, insert_antisense):
        start, end = offset + 1, offset + len(part)
        loc = f"complement({start}..{end})" if antisense else f"{start}..{end}"
        features.append(_feat("misc_feature", loc, label))
        offset += len(part)

    new_seq = seq[:stuffer_start - 1] + insert_seq + seq[stuffer_end:]
    name = f"pESC-HIS-ENCORE-{nc_id}"
    definition = (
        f"Real {backbone['label']} ({backbone['length_bp']}bp) with its stuffer cassette "
        f"(between {oh5['label']} and {oh3['label']}) replaced by the assembled construct. "
        "Junction accuracy depends on CARGO_L1_FLANK/NC_L1_FLANK/PROMO_FLANK matching the "
        f"real {oh5['label']}/{oh3['label']} overhangs — not yet verified, see PROJECT_TODO.txt section 1."
    )
    return name, new_seq, features, True, definition
