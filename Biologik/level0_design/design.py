from __future__ import annotations

"""Level-0-Design-Logik für die Erstellung von Golden-Gate-Modulen in Python."""

from typing import List

from .data import (
    BSAI_PRIMER_PREFIX,
    CARGO_L1_FLANK,
    LINKERS,
    NC_L1_FLANK,
    NOMINAL_BP,
    PROMO_FLANK,
    TYPE_OVERHANGS,
    find_linker,
    find_nanocompartment,
    find_promoter,
)
from .sequence import reverse_complement, validate_cargo, wallace_tm


def level0_part(slot: int, spec: dict) -> dict:
    # Funktion zur Erstellung eines Level-0-Moduls, eine Art Steckbrief.
    # TYPE_OVERHANGS enthält die festen Überhänge für jeden Slot eines Level-0-Parts.
    overhang5, overhang3 = TYPE_OVERHANGS[slot]
    return {
        "slot": slot,
        "type": f"Type {slot}",
        "role": spec["role"],
        "label": spec["label"],
        "kind": spec["kind"],
        "note": spec["note"],
        "bp": spec["bp"],
        "overhang5": overhang5,
        "overhang3": overhang3,
        "surface": spec.get("surface", False),
        "isCargo": spec.get("isCargo", False),
    }


def build_modules(nc: dict, link: dict, cargo_label: str, cargo_bp: int, fusion: str):
    # Ein Modul besteht aus mehreren Level-0-Teilen. Hier werden die Bausteine für Cargo- und NC-Modul aufgebaut.
    tp = {"role": "targeting-peptide", "label": nc["tp"], "kind": "t1", "note": "Targeting peptide", "bp": NOMINAL_BP["TP"]}
    lk = {"role": "linker", "label": link["label"], "kind": "t2", "note": f"{link['aa']} aa", "bp": link["bp"]}
    cg = {"role": "cargo", "label": cargo_label, "kind": "t3", "note": f"{cargo_bp} bp", "bp": cargo_bp, "isCargo": True}

    def ncs():
        # Eine verschachtelte Funktion ist eine kleine Hilfe-Funktion innerhalb einer anderen Funktion.
        return {"role": "ncs", "label": "NCS", "kind": "ncs", "note": "Spacer", "bp": NOMINAL_BP["NCS"]}

    def surf(label: str = "NCS"):
        return {"role": "surface", "label": label, "kind": "ncs", "note": "open · e.g. SpyCatcher", "bp": NOMINAL_BP["NCS"], "surface": True}

    cargo_layout = [tp, lk, cg, ncs(), ncs()] if fusion == "C" else [ncs(), ncs(), cg, lk, tp]
    # Eine List-Comprehension baut aus einer Liste schnell eine Liste mit verarbeiteten Elementen.
    cargo_module = [level0_part(index + 1, spec) for index, spec in enumerate(cargo_layout)]

    nc_layout = [surf(), surf(), {"role": "shell", "label": nc["shell"], "kind": "shell", "note": f"{nc['shellBp']} bp", "bp": nc["shellBp"]}, surf("NCS*"), surf()]
    nc_module = [level0_part(index + 1, spec) for index, spec in enumerate(nc_layout)]
    return cargo_module, nc_module


def _wallace_primer_pair(sequence: str, oh_f: str, oh_r: str):
    """Grobe Abschaetzung ueber die Wallace-Regel (2 °C je A/T, 4 °C je G/C).

    Fallback, wenn primer3 nicht installiert ist oder kein Paar findet. Reicht
    fuer die Vorschau, nicht fuer die Bestellung.
    """
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


def build_plate_plan(nc: dict, link: dict, cargo_label: str):
    # Der 96-Well-Plan sagt, welche Bausteine aus dem Stock-Plate für die Assemblierung benötigt werden.
    return [
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


def build_order_list(nc: dict, link: dict, cargo_module: List[dict], cargo_label: str, cargo_bp: int, cargo_seq: str):
    # Eine innere Funktion hilft, die Auswahl eines bestimmten Bausteins aus dem Modul zu kapseln.
    def role_type(role: str):
        match = next((part for part in cargo_module if part["role"] == role), None)
        return match["type"] if match else None

    return {
        "fixed": [
            {"name": f"Targeting peptide {nc['tp']}", "sub": f"{role_type('targeting-peptide') or 'Type 1/5'} · standard module", "kind": "t1"},
            {"name": f"Linker {link['label']}", "sub": f"{role_type('linker') or 'Type 2/4'} · standard module", "kind": "t2"},
            {"name": f"Shell CDS {nc['shell']}", "sub": "Nanocompartment · standard module", "kind": "shell"},
            {"name": "Promoter GAL1-10", "sub": "bidirectional · standard module", "kind": "promo"},
            {"name": "NCS / surface slot", "sub": "Spacer or display marker (e.g. SpyCatcher)", "kind": "ncs"},
        ],
        "new": {
            "name": f"{cargo_label} ({cargo_bp} bp)",
            "sub": "Type 3 · your new cargo — synthesis/PCR with overhangs",
            "kind": "t3",
            "cargoWithOverhangs": f"{CARGO_L1_FLANK[0]}{cargo_seq}{CARGO_L1_FLANK[1]}",
            "overhangs": {"left": CARGO_L1_FLANK[0], "right": CARGO_L1_FLANK[1]},
        },
    }


def design_construct(decisions: dict = None):
    # Der Hauptaufbau: Aus den Eingaben wird ein kompletter Design-Plan erzeugt.
    decisions = decisions or {}
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

    cargo_module, nc_module = build_modules(nc, link, cargo_label, cargo_bp, fusion)
    primers = make_primer_pair(cargo["clean"], CARGO_L1_FLANK[0], CARGO_L1_FLANK[1])

    # Die Cargo-Validierung liefert eigene Warnungen; die Primer-Methode kommt dazu,
    # damit im UI erkennbar ist, ob echte Thermodynamik oder nur eine Schaetzung dahintersteht.
    design_warnings = list(cargo["warnings"])
    if primers and primers[0].get("tmMethod") == "wallace":
        design_warnings.append(
            "primer3 is not available — Tm values are rough Wallace estimates (preview only). "
            "Install primer3-py (see Biologik/requirements.txt) for nearest-neighbor Tm, "
            "dimer/hairpin checks and the Q5 annealing temperature."
        )

    return {
        "input": {"nanocompartment": nc["id"], "fusion": fusion, "linker": link["id"], "promoter": promoter_entry["id"], "cargoLabel": cargo_label},
        "nanocompartment": {"id": nc["id"], "label": nc["label"], "T": nc["T"], "dia": nc["dia"], "shell": nc["shell"], "shellBp": nc["shellBp"]},
        "targetingPeptide": nc["tp"],
        "linker": {"id": link["id"], "label": link["label"], "aa": link["aa"], "bp": link["bp"]},
        "cargo": {"label": cargo_label, "sequence": cargo["clean"], "bp": cargo_bp, "aa": cargo["aa"], "gc": cargo["gc"], "validation": cargo},
        "fusion": fusion,
        "level0": {"total": len(cargo_module) + len(nc_module), "cargoModule": cargo_module, "ncModule": nc_module},
        "level1": {"cargoModule": {"role": f"{fusion}-terminal cargo module", "enzyme": "BsaI", "flanks": {"left": CARGO_L1_FLANK[0], "right": CARGO_L1_FLANK[1]}, "parts": cargo_module}, "ncModule": nc_module},
        "level2": {"promoter": {"id": promoter_entry["id"], "label": promoter_entry["label"], "kind": "promo", "bp": NOMINAL_BP["PROMO"], "flanks": {"left": PROMO_FLANK[0], "right": PROMO_FLANK[1]}}},
        "primers": primers,
        "platePlan": build_plate_plan(nc, link, cargo_label),
        "orderList": build_order_list(nc, link, cargo_module, cargo_label, cargo_bp, cargo["clean"]),
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
    cargo_seq = design["cargo"]["sequence"]
    cargo_name = design["cargo"]["label"].replace(" ", "-")

    tp_seq = placeholder_seq("TP" + design["targetingPeptide"], 36)
    link_seq = placeholder_seq("LINK" + link["id"], link["bp"])
    shell_seq = placeholder_seq("SHELL" + nc["shell"], nc["shellBp"])
    promo_seq = placeholder_seq("PROMO" + design["level2"]["promoter"]["id"], 600)
    ncs_seq = placeholder_seq("NCS", 30)

    add(f"Targeting-Peptide_{design['targetingPeptide']} [Type1/5] [PLACEHOLDER]", tp_seq)
    add(f"Linker_{link['id']} [Type2/4] [PLACEHOLDER]", link_seq)
    add(f"Cargo_{cargo_name} [Type3] [REAL INPUT {len(cargo_seq)}bp]", cargo_seq)
    add(f"Nanocompartment-Shell_{nc['shell']} [PLACEHOLDER]", shell_seq)
    add(f"Promoter_{design['level2']['promoter']['label']} [bidirectional] [PLACEHOLDER]", promo_seq)
    add("NCS-Spacer [PLACEHOLDER]", ncs_seq)
    add(f"Cargo_{cargo_name}_with-overhangs", f"{CARGO_L1_FLANK[0]}{cargo_seq}{CARGO_L1_FLANK[1]}")

    cargo_module_seq = tp_seq + link_seq + cargo_seq + ncs_seq + ncs_seq if design["fusion"] == "C" else ncs_seq + ncs_seq + cargo_seq + link_seq + tp_seq
    nc_module_seq = ncs_seq + ncs_seq + shell_seq + ncs_seq + ncs_seq
    add(f"Level1_Cargo-Module_{design['fusion']}-terminal [{design['cargo']['label']}]", cargo_module_seq)
    add("Level1_Nanocompartment-Module [" + nc["shell"] + "]", nc_module_seq)

    level2 = reverse_complement(cargo_module_seq) + promo_seq + nc_module_seq
    add(f"Level2_pESC-ENCORE-{nc['id']}_COMPLETE [~{len(level2)}bp] [Cargo(rev)<-promoter->NC]", level2)

    banner = "; ENCORE Builder — FASTA export (prototype)\n; Standard modules are PLACEHOLDER sequences; only the cargo is real input.\n"
    return banner + "\n".join(output)
