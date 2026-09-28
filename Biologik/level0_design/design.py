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


def fasta_wrap(sequence: str, width: int = 70) -> str:
    return "\n".join(sequence[index:index + width] for index in range(0, len(sequence), width))


def build_fasta(design: dict) -> str:
    # FASTA ist ein einfaches Format für DNA-Sequenzen. Hier wird eine Export-Datei für die Bausteine gebaut.
    # Eine Funktion kann einen neuen String aus mehreren Teilen zusammensetzen.
    output = []

    def add(header: str, sequence: str):
        output.append(f">{header}\n{fasta_wrap(sequence)}")

    nc = design["nanocompartment"]
    cargo_sense = design["cargo"]["sequence"]
    cargo_seq = design["cargo"]["sequenceAntisense"]
    cargo_name = design["cargo"]["label"].replace(" ", "-")

    shell_seq = nc["sequence"] if nc.get("custom") else placeholder_seq("SHELL" + nc["shell"], nc["shellBp"])
    promo_seq = placeholder_seq("PROMO" + design["level2"]["promoter"]["id"], 600)
    ncs_seq = placeholder_seq("NCS", 30)
    tp_seq = placeholder_seq("TP" + design["targetingPeptide"], 36)
    cargo_slots = {entry["slot"]: entry for entry in design["cargoSlots"]}
    nc_slots = {entry["slot"]: entry for entry in design["ncSlots"]}

    def slot_seq(entry: dict) -> str:
        if entry["kind"] == "custom":
            return entry["sequence"]
        if entry["kind"] == "tp":
            return tp_seq
        if entry["kind"] == "linker":
            return placeholder_seq("LINK" + entry["id"], entry["bp"])
        if entry["kind"] == "marker":
            return placeholder_seq("MARK" + entry["id"], entry["bp"])
        return ncs_seq

    def add_slot_records(slots: dict, where: str, antisense: bool):
        for n in (1, 2, 4, 5):
            entry = slots[n]
            tag = f"Type0.{n}"
            if entry["kind"] == "tp":
                add(f"Targeting-Peptide_{design['targetingPeptide']} [{tag}] [{where}] [PLACEHOLDER]", slot_seq(entry))
            elif entry["kind"] == "linker":
                add(f"Linker_{entry['id']} [{tag}] [{where}] [PLACEHOLDER {entry['bp']}bp]", slot_seq(entry))
            elif entry["kind"] == "marker":
                add(f"Surface-Marker_{entry['label']} [{tag}] [{where}] [PLACEHOLDER {entry['bp']}bp]", slot_seq(entry))
            elif entry["kind"] == "custom":
                label = entry["label"].replace(" ", "-")
                seq = reverse_complement(entry["sequence"]) if antisense else entry["sequence"]
                # pESC-eigene Strangbenennung: die Cargo sitzt auf dem Antisense-Strang von MCS1, daher ist das
                # Reverse Complement (das hier bestellt wird) der SENSE-Strang von pESC — nicht der Gen-Sense-Strang.
                note = " [SENSE = reverse complement of the input]" if antisense else ""
                add(f"Custom-Part_{label} [{tag}] [{where}] [REAL INPUT {entry['bp']}bp]{note}", seq)
                add(f"Custom-Part_{label}_with-overhangs [{JUNCTION_OVERHANGS[n - 1]}...{JUNCTION_OVERHANGS[n]}]",
                    f"{JUNCTION_OVERHANGS[n - 1]}{seq}{JUNCTION_OVERHANGS[n]}")

    add(f"Cargo_{cargo_name} [Type0.3] [REAL INPUT {len(cargo_seq)}bp] [SENSE = reverse complement of the input CDS]", cargo_seq)
    add(f"Cargo_{cargo_name}_input-CDS [reference only] [{len(cargo_sense)}bp]", cargo_sense)
    add_slot_records(cargo_slots, "cargo module", antisense=True)
    if nc.get("custom"):
        name = nc["shell"].replace(" ", "-")
        add(f"Nanocompartment-Shell_{name} [Type0.3] [REAL INPUT {len(shell_seq)}bp]", shell_seq)
        add(f"Nanocompartment-Shell_{name}_with-overhangs [{JUNCTION_OVERHANGS[2]}...{JUNCTION_OVERHANGS[3]}]",
            f"{JUNCTION_OVERHANGS[2]}{shell_seq}{JUNCTION_OVERHANGS[3]}")
    else:
        add(f"Nanocompartment-Shell_{nc['shell']} [PLACEHOLDER]", shell_seq)
    add(f"Promoter_{design['level2']['promoter']['label']} [bidirectional] [PLACEHOLDER]", promo_seq)
    add("NCS-Spacer [PLACEHOLDER]", ncs_seq)
    add_slot_records(nc_slots, "nanocompartment site", antisense=False)
    add(f"Cargo_{cargo_name}_with-overhangs [sense]", f"{CARGO_L1_FLANK[0]}{cargo_seq}{CARGO_L1_FLANK[1]}")

    # Das Cargo-Modul liegt im Level-2-Konstrukt auf dem Antisense-Strang: die Top-Strand-Sequenz
    # ist die Typ-Reihenfolge 1..5, jedes Teil als Reverse Complement (das Cargo ist schon
    # Antisense). Es wird danach NICHT noch einmal umgedreht.
    slot_order = [slot_seq(cargo_slots[1]), slot_seq(cargo_slots[2]), cargo_sense, slot_seq(cargo_slots[4]), slot_seq(cargo_slots[5])]
    cargo_module_seq = "".join(reverse_complement(part) for part in slot_order)
    # NC-Modul (Sense): Slots 1, 2, Shell, 4, 5 in Typ-Reihenfolge.
    nc_module_seq = slot_seq(nc_slots[1]) + slot_seq(nc_slots[2]) + shell_seq + slot_seq(nc_slots[4]) + slot_seq(nc_slots[5])
    add(f"Level1_Cargo-Module [{design['cargo']['label']}]", cargo_module_seq)
    add("Level1_Nanocompartment-Module [" + nc["shell"] + "]", nc_module_seq)

    level2 = cargo_module_seq + promo_seq + nc_module_seq
    add(f"Level2_pESC-ENCORE-{nc['id']}_COMPLETE [~{len(level2)}bp] [Cargo(rev)<-promoter->NC]", level2)

    banner = "; ENCORE Builder — FASTA export (prototype)\n; Standard modules are PLACEHOLDER sequences; the cargo and any own sequences are real input.\n"
    return banner + "\n".join(output)
