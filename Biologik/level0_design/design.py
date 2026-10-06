from __future__ import annotations

"""Level-0-Design-Logik für die Erstellung von Golden-Gate-Modulen in Python."""

import re

from .data import (
    NANOCOMPARTMENTS,
    BSAI_PRIMER_PREFIX,
    CARGO_L1_FLANK,
    NOMINAL_BP,
    find_intein,
    find_linker,
    find_nanocompartment,
    find_promoter,
    find_surface_marker,
)
# Sequence-py enthält Funktionen für die Verarbeitung von DNA-Sequenzen
# Z.B. zum Bilden von Komplementären DNA-Sequenzen, zur Berechnung der Schmelztemperatur
from .sequence import reverse_complement, validate_cargo, wallace_tm
from .parts_db import find_inserts, find_part, find_real_sequence, load_parts
from .assembly import assemble_level1_module, assemble_level1_promoter, assemble_level2, finish_level1, level1_fragment
from .genbank_writer import format_genbank_record, location_span, make_feature as _feat, shift_location


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
        elif kind == "intein":
            item = find_intein(cfg.get("id"))
            if not item:
                raise ValueError(f"Type 0.{n}: unknown intein \"{cfg.get('id')}\".")
            slots[n] = {"kind": "intein", "id": item["id"], "label": item["label"], "aa": item["aa"], "bp": item["bp"]}
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


def _wallace_anneal(sequence: str):
    """Annealing-Teile (vorwaerts, rueckwaerts) ueber die Wallace-Regel (2 °C je A/T, 4 °C je G/C).

    Fallback, wenn primer3 nicht installiert ist oder kein Paar findet. Reicht
    fuer die Vorschau, nicht fuer die Bestellung. Gibt (anneal_f, anneal_r, balanced) zurueck.
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
    return sequence[:len_f], reverse_complement(sequence[-len_r:]), balanced


_WALLACE_HINT = (
    "Hinweis: Die automatische Anpassung der Primer-Längen konnte die Schmelztemperaturen nicht auf "
    "weniger als 5°C Differenz bringen. Überprüfe die Primer manuell oder passe die Sequenz/Annealing-Längen an."
)


def _wallace_primer_pair(sequence: str, oh_f: str, oh_r: str):
    anneal_f, anneal_r, balanced = _wallace_anneal(sequence)
    primers = _assemble_primers(anneal_f, anneal_r, oh_f, oh_r, wallace_tm(anneal_f), wallace_tm(anneal_r))
    for primer in primers:
        primer["tmMethod"] = "wallace"
        if not balanced:
            primer["note"] = _WALLACE_HINT

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
    Type-3-Overhang). Welche Variante die reale Toolbox
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


# 5'-Polster vor der BbsI-Erkennungsstelle: Restriktionsenzyme schneiden am Ende eines PCR-Produkts
# schlecht, wenn die Erkennungsstelle direkt am Rand liegt.
PCR_CLAMP = "TTTT"
# Unterhalb dieser Laenge ist PCR unpraktisch (Primer ueberlappen) -> als annealte Oligos bestellen.
MIN_PCR_INSERT_BP = 40
_INTERNAL_SITES = {"BbsI": ("GAAGAC", "GTCTTC"), "BsaI": ("GGTCTC", "GAGACC")}


def resolve_insert(category: str, part: str, site: str, slot: int, seed: str, length: int, **extra) -> tuple:
    """(Teilsequenz in Sense-Richtung, ist_echt, Lagerstatus) eines Toolkit-Teils fuer eine Site ("nc_site"/"cargo_site") und
    einen Type-Slot aus der Datenbank parts/level0_inserts/. Gibt es genau dort ein Level-0-Plasmid, kommt dessen Insert und
    sein Lagerstatus (on_stock). Sonst die Sequenz desselben Teils von einer anderen Site/einem anderen Slot (Lagerstatus
    False: an dieser Stelle gibt es kein Plasmid), und ohne jeden Treffer eine deterministische Platzhalter-Sequenz."""
    exact = find_inserts(category, part, site, slot, **extra)
    if exact:
        return exact[0]["sequence"], True, exact[0].get("on_stock")
    other = (find_inserts(category, part, site, **extra) or find_inserts(category, part, **extra)
             or (find_inserts(category, part, site) or find_inserts(category, part) if "variant" not in extra else []))
    if other:
        return other[0]["sequence"], True, False
    return placeholder_seq(seed, length), False, None


def design_level0_oligos(built: dict, label: str, slot: int, module: str) -> dict:
    """Zwei komplementaere Oligos fuer ein Teil, das zu kurz fuer PCR-Primer ist: nach dem Annealen entsteht direkt das
    BbsI-geschnittene Fragment (Overhangs 0N/0C als 5'-Ueberstaende), das ohne weiteren Verdau ins Level-0-Backbone
    ligiert. Oben: vom 0N-Overhang bis kurz vor den 0C-Overhang; unten: Reverse Complement alles hinter 0N bis einschliesslich 0C."""
    roles = {o["role"]: o for o in built["overhangs"]}
    n0, n1 = location_span(roles["level0_N"]["location"])
    c0, c1 = location_span(roles["level0_C"]["location"])
    seq = built["sequence"]
    top, bottom = seq[n0 - 1:c0 - 1], reverse_complement(seq[n1:c1])
    base = level0_record_name(label, slot, module, "Oligo")
    return {
        "possible": True,
        "top": {"name": f"{base}_F", "sequence": top, "length": len(top)},
        "bottom": {"name": f"{base}_R", "sequence": bottom, "length": len(bottom)},
        "overhangs": {"left": seq[n0 - 1:n1], "right": reverse_complement(seq[c0 - 1:c1])},
        "annealedLength": len(seq[n0 - 1:c1]),
    }


def level0_record_name(label: str, slot: int, module: str, kind: str = "") -> str:
    """Name eines Level-0-Records, an dem man Type und Site direkt erkennt: z.B. Level0.2_NCS_Cargo / Level0.2_NCS_NC
    (mit `kind="Primers"`: Level0.2_Primers_NCS_Cargo). `module` ist "cargo"/"nc" (oder "cargo_site"/"nc_site")."""
    site = "Cargo" if module.startswith("cargo") else "NC"
    clean = re.sub(r"[^A-Za-z0-9.-]+", "-", label.replace("×", "x")).strip("-") or "part"
    return "_".join(filter(None, (f"Level0.{slot}", kind, clean, site)))


def design_level0_primers(shown: dict, label: str, slot: int, module: str):
    """PCR-Primer, die eine vorhandene Teilsequenz (`shown["insert"]`, 5'->3' im Konstrukt) Level-0-kompatibel
    machen: 5'-Ueberhang = Polster + gesamte Adapter-Flanke vor/hinter dem Insert (BbsI-Stelle, Level-0-/
    Level-1-/ggf. Level-2-Overhangs, BsaI-Stelle), 3'-Teil = Annealing an das Insert (primer3, sonst Wallace).
    Das PCR-Produkt entspricht `shown["sequence"]` plus je ein Polster, kann also direkt mit BbsI ins
    Level-0-Backbone kloniert werden. Gibt `{"possible": False, "reason": ...}` zurueck, wenn das Insert
    fuer PCR zu kurz ist."""
    insert = shown["insert"]["sequence"]
    if len(insert) < MIN_PCR_INSERT_BP:
        return {"possible": False,
                "reason": f"Insert is only {len(insert)} bp — too short for PCR. Order it as two annealed oligos "
                          f"carrying the same overhangs instead."}
    start, end = location_span(shown["insert"]["location"])
    ext_f = PCR_CLAMP + shown["sequence"][:start - 1]
    ext_r = PCR_CLAMP + reverse_complement(shown["sequence"][end:])

    result = None
    try:
        from ..primer_design import design_primers
        result = design_primers(sequence=insert, ext_fw=ext_f, ext_rv=ext_r)
    except (ImportError, ValueError):
        pass                       # primer3 fehlt oder kein Paar -> Wallace
    if result:
        anneal_f, anneal_r = result["annealFw"], result["annealRv"]
        tm_f, tm_r, method = round(result["tmFw"], 1), round(result["tmRv"], 1), "primer3-nn"
        q5 = round(result["q5AnnealingTemp"], 1)
        issues = list(result["issues"])
    else:
        anneal_f, anneal_r, balanced = _wallace_anneal(insert)
        tm_f, tm_r, method, q5 = wallace_tm(anneal_f), wallace_tm(anneal_r), "wallace", None
        issues = [] if balanced else [_WALLACE_HINT]

    def primer(name: str, ext: str, anneal: str, tm) -> dict:
        return {"name": name, "sequence": ext + anneal, "extension": ext, "anneal": anneal,
                "length": len(ext) + len(anneal), "annealLength": len(anneal), "tm": tm}

    base = level0_record_name(label, slot, module)
    sites = [f"{enzyme} site ({site})" for enzyme, pair in _INTERNAL_SITES.items()
             for site in pair if site in insert]
    return {
        "possible": True,
        "forward": primer(f"{base}_F", ext_f, anneal_f, tm_f),
        "reverse": primer(f"{base}_R", ext_r, anneal_r, tm_r),
        "clamp": PCR_CLAMP,
        "productLength": len(PCR_CLAMP) * 2 + shown["length"],
        "tmMethod": method, "q5AnnealingTemp": q5,
        "valid": not issues, "issues": issues,
        "internalSites": sites,
    }


def pcr_product_genbank(shown: dict, primers: dict, label: str, slot: int, module: str, adapter_id: str, features: list) -> str:
    """GenBank-Record des PCR-Produkts (Polster + Konstrukt + Polster, linear) mit beiden Primern als
    `primer_bind` ueber ihre volle Laenge (Polster + Adapter-Flanke + Annealing-Teil). `features` sind die
    Konstrukt-Features (BbsI-Stellen, Overhangs, Insert) in Konstrukt-Koordinaten; sie werden um das Polster
    verschoben."""
    clamp = primers["clamp"]
    sequence = clamp + shown["sequence"] + clamp
    out = [{**f, "location": shift_location(f["location"], len(clamp))} for f in features]
    f, r = primers["forward"], primers["reverse"]
    total = len(sequence)
    for primer, loc in ((f, f"1..{f['length']}"), (r, f"complement({total - r['length'] + 1}..{total})")):
        out.append(_feat("primer_bind", loc, primer["name"],
                         f"{primer['name']} 5'-{primer['sequence']}-3' · {len(clamp)}-nt clamp + adapter {adapter_id} flank + "
                         f"{primer['annealLength']}-nt annealing part · Tm {primer['tm']} °C ({primers['tmMethod']})"))
    out.sort(key=lambda x: location_span(x["location"])[0])
    definition = (f"PCR product of {label} (Type 0.{slot}, adapter {adapter_id}) with its two PCR primers: "
                  f"{len(clamp)}-nt clamp + BbsI site/overhangs + insert. Clone with BbsI into the Level 0 backbone.")
    return format_genbank_record(level0_record_name(label, slot, module, "Primers"), sequence, out, False, definition)


def _slot_summary(slots: dict) -> list:
    return [
        {"slot": n, **{k: v for k, v in slots[n].items() if k not in ("seq", "validation")},
         **({"sequence": slots[n]["seq"], "isNew": True} if slots[n]["kind"] == "custom" else {})}
        for n in NC_SLOTS
    ]


def _first_backbone(kind: str):
    backbone = next(iter(load_parts()[kind]), None)
    return backbone if backbone and backbone.get("sequence") else None


def build_level1_and_2(fragments: list, promoter_entry: dict, nc: dict):
    """Level 1: Cargo-Modul, NC-Modul und Promotor je als Insert (+ Plasmid) im Level-1-Backbone (BsaI);
    Level 2: die drei Inserts im Level-2-Backbone (BbsI). Ohne Level-1-Backbone in der Datenbank: ([], None)."""
    backbone1 = _first_backbone("level1_backbones")
    if not backbone1:
        return [], None
    backbone2 = _first_backbone("level2_backbones")
    by_module = {m: [f for f in fragments if f["module"] == m] for m in ("cargo", "nc")}
    cargo = finish_level1(assemble_level1_module(by_module["cargo"], "Cargo module", "cargo_site", True, "Level1_Cargo"), backbone1)
    ncm = finish_level1(assemble_level1_module(by_module["nc"], "Nanocompartment module", "nc_site", False, "Level1_NC"), backbone1)
    promo_seq, promo_real = resolve_seq("promoters", promoter_entry["id"], "PROMO" + promoter_entry["id"], NOMINAL_BP["PROMO"])
    promo = finish_level1(assemble_level1_promoter(promoter_entry["label"], promo_seq, promo_real, "Level1_Promoter", backbone1), backbone1)
    level2 = assemble_level2([cargo, promo, ncm], f"ENCORE-{nc['id']}", backbone2)
    return [cargo, promo, ncm], level2


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

    fragments: list = []
    level0_constructs = build_level0_constructs(nc, cargo_label, cargo_antisense, cargo_slots, nc_slots, fragments)
    level1_constructs, level2_construct = build_level1_and_2(fragments, promoter_entry, nc)

    return {
        "nanocompartment": {"id": nc["id"], "label": nc["label"], "T": nc["T"], "dia": nc["dia"], "shell": nc["shell"], "shellBp": nc["shellBp"],
                            "custom": bool(nc.get("custom")),
                            **({"sequence": nc["seq"]} if nc.get("custom") else {})},
        "targetingPeptide": nc["tp"],
        "cargo": {"label": cargo_label, "sequence": cargo["clean"], "sequenceAntisense": cargo_antisense, "bp": cargo_bp},
        "level0": {"cargoModule": cargo_module, "ncModule": nc_module},
        "level2": {"promoter": {"id": promoter_entry["id"], "label": promoter_entry["label"], "bp": NOMINAL_BP["PROMO"]}},
        "cargoSlots": _slot_summary(cargo_slots),
        "ncSlots": _slot_summary(nc_slots),
        "primers": primers,
        "level0Constructs": level0_constructs,
        "level1Constructs": level1_constructs,
        "level2Construct": level2_construct,
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


def attach_adapter(adapter, insert_seq: str) -> dict:
    """Haengt die Overhang-Flanken eines Type-Adapters (parts/type_overhangs/) an eine CDS bzw.
    Teilsequenz: der 4-nt-Platzhalter ("Insert", z.B. AAAA) wird durch die Sequenz ersetzt.

    `adapter` ist die id ("0.1", "0.1rc", "0.2", ...) oder der bereits geladene Eintrag. Die Sequenz
    wird unveraendert eingesetzt — die Orientierung (bei den rc-Adaptern der Cargo Site) liegt beim
    Aufrufer. Alle Features hinter dem Insert werden um die Laengendifferenz verschoben; am Ende wird
    jeder Overhang und jede BbsI-Stelle gegen die neue Sequenz geprueft, damit eine verrutschte
    Position nie still durchgeht."""
    entry = adapter if isinstance(adapter, dict) else find_part("type_overhangs", adapter)
    if not entry or not entry.get("sequence"):
        raise ValueError(f"Unbekannter oder leerer Overhang-Adapter: {adapter!r}")
    adapter_id, seq = entry["id"], entry["sequence"]

    cds = (insert_seq or "").upper()
    if not cds or set(cds) - set("ACGT"):
        raise ValueError("Die Insert-Sequenz muss aus A/C/G/T bestehen und darf nicht leer sein.")

    start, end = location_span(entry["insert"]["location"])
    placeholder = entry["insert"]["placeholder_sequence"]
    if seq[start - 1:end] != placeholder:
        raise ValueError(f"Adapter {adapter_id}: an {start}..{end} steht nicht der Platzhalter {placeholder}.")

    shift = len(cds) - (end - start + 1)
    new_seq = seq[:start - 1] + cds + seq[end:]

    def moved(location: str) -> str:
        a, b = location_span(location)
        if b < start:
            return location
        if a > end:
            return shift_location(location, shift)
        raise ValueError(f"Adapter {adapter_id}: Feature {location} ueberlappt den Insert-Platzhalter.")

    insert_location = f"{start}..{end + shift}"
    features = []
    for f in entry["features"]:
        if f["location"] == entry["insert"]["location"]:
            features.append({**f, "location": insert_location})
        else:
            features.append({**f, "location": moved(f["location"])})
    overhangs = [{**o, "location": moved(o["location"])} for o in entry["overhangs"]]
    bbsi_sites = [{**b, "location": moved(b["location"])} for b in entry["bbsi_sites"]]

    for item in overhangs + bbsi_sites:
        a, b = location_span(item["location"])
        if new_seq[a - 1:b] != item["sequence_top_strand"]:
            raise ValueError(f"Adapter {adapter_id}: {item['location']} stimmt nach dem Einsetzen nicht mehr.")

    return {
        "adapter": adapter_id,
        "usedForModules": entry["used_for_modules"],
        "sequence": new_seq,
        "length": len(new_seq),
        "insert": {"location": insert_location, "sequence": cds},
        "overhangs": overhangs,
        "bbsiSites": bbsi_sites,
        "spacers": [dict(entry["frame_spacer"])] if entry.get("frame_spacer") else [],
        "features": features,
    }


def adapter_id_for(module: str, slot: int) -> str:
    """Welcher Adapter (parts/type_overhangs/) fuer ein Teil in Modul `module` ("cargo"/"nc") an Type 0.<slot>
    gilt: an den Aussenslots 0.1/0.5 haben die Cargo Site eigene rc-Adapter, 0.2-0.4 gelten fuer beide Seiten."""
    return f"0.{slot}rc" if module == "cargo" and slot in (1, 5) else f"0.{slot}"


def clone_into_level0_backbone(built: dict, label: str, backbone: dict, antisense: bool = False, name: str | None = None) -> dict:
    """BbsI-Klonierung eines Adapter-Konstrukts (attach_adapter) ins Level-0-Backbone.

    BbsI schneidet aus dem Backbone den Stuffer heraus (die Stelle zwischen den Akzeptor-Overhangs
    NLvl0/CLvl0) und aus dem Konstrukt das Fragment vom Level-0-N- bis zum Level-0-C-Overhang — die
    BbsI-Erkennungsstellen des Adapters bleiben im verworfenen Rest zurueck. Die vier-Basen-Enden
    beider Fragmente sind identisch und ligieren: Plasmid = Backbone bis vor NLvl0 + Fragment + Backbone
    ab nach CLvl0. An den Naehten entstehen die BsaI-Stellen fuer Level 1 neu (GGT|CTC und GAGACC).
    Annotationen: alles vom Backbone, was ausserhalb des herausgeschnittenen Bereichs liegt, plus die
    Overhangs und das Insert aus dem Adapter. Features im Stuffer (lacZ-alpha, MCS, BbsI-Stellen, ...)
    sind mit dem Stuffer verschwunden. Die Sequenz ist immer der Top-Strand, 5' links -> 3' rechts;
    `antisense` (Cargo-Modul): das Insert liegt im Backbone-Top-Strand antisense -> CDS-Feature mit complement()."""
    seq = backbone["sequence"]
    oh5 = backbone["receiver_overhangs"]["5_prime"]
    oh3 = backbone["receiver_overhangs"]["3_prime"]
    bb_n0, bb_n1 = location_span(oh5["location"])
    bb_c0, bb_c1 = location_span(oh3["location"])
    roles = {o["role"]: o for o in built["overhangs"]}
    ad_n0, _ = location_span(roles["level0_N"]["location"])
    _, ad_c1 = location_span(roles["level0_C"]["location"])
    if seq[bb_n0 - 1:bb_n1] != roles["level0_N"]["sequence_top_strand"] or \
            seq[bb_c0 - 1:bb_c1] != roles["level0_C"]["sequence_top_strand"]:
        raise ValueError(f"Adapter {built['adapter']}: Level-0-Overhangs passen nicht zum Backbone {backbone['id']}.")

    fragment = built["sequence"][ad_n0 - 1:ad_c1]
    new_seq = seq[:bb_n0 - 1] + fragment + seq[bb_c1:]
    tail_shift = len(fragment) - (bb_c1 - bb_n0 + 1)
    adapter_to_plasmid = bb_n0 - ad_n0
    insert_start, insert_end = bb_n0, bb_n0 + len(fragment) - 1

    features = []
    for f in backbone.get("features", []):
        lo, hi = location_span(f["location"])
        lab = (f["qualifiers"].get("label") or [""])[0]
        loc = None
        if f["type"] == "source":
            loc = f"1..{len(new_seq)}"
        elif hi < bb_n0:
            loc = f["location"]
        elif lo > bb_c1:
            loc = shift_location(f["location"], tail_shift)
        elif lab == "BsaI rec site":
            # die beiden BsaI-Stellen ragen an der Naht in den Austauschbereich hinein; die Basen werden von
            # Backbone und Fragment gemeinsam neu zusammengesetzt (GGT|CTC bzw. GAG|ACC) — Stelle bleibt erhalten
            loc = f["location"] if lo < bb_n0 else shift_location(f["location"], tail_shift)
            a, b = location_span(loc)
            site = new_seq[a - 1:b]
            if (reverse_complement(site) if loc.startswith("complement(") else site) != "GGTCTC":
                raise ValueError(f"BsaI-Stelle {loc} ist nach dem Klonieren nicht intakt.")
        if loc is not None:
            quals = [(k, v) for k, vals in f["qualifiers"].items() if k != "translation" for v in vals]
            features.append({"type": f["type"], "location": loc, "qualifiers": quals})

    for o in built["overhangs"]:
        features.append(_feat("overhang", shift_location(o["location"], adapter_to_plasmid), o["label"],
                              f"{o['role']} · top strand {o['sequence_top_strand']}"))
    for sp in built.get("spacers", []):
        features.append(_feat("misc_feature", shift_location(sp["location"], adapter_to_plasmid), "Frame spacer", sp["note"]))
    insert_loc = shift_location(built["insert"]["location"], adapter_to_plasmid)
    features.append(_feat("CDS", f"complement({insert_loc})" if antisense else insert_loc, label,
                          f"Insert cloned via BbsI into {backbone['id']} · adapter {built['adapter']} · "
                          + ("antisense: the ORF reads on the complement strand" if antisense else "sense strand")))
    features.sort(key=lambda f: (location_span(f["location"])[0], location_span(f["location"])[1]))

    for f in features:
        a, b = location_span(f["location"])
        if a < 1 or b > len(new_seq):
            raise ValueError(f"Feature {f['location']} liegt ausserhalb des Plasmids.")

    name = name or f"{backbone['id'].split('-')[0]}-{label.replace(' ', '-')}"
    definition = (f"{backbone['label']} with {label} cloned in via BbsI (adapter {built['adapter']}): the "
                  f"{bb_c1 - bb_n0 + 1} bp stuffer between {oh5['label']} and {oh3['label']} is replaced by "
                  f"{len(fragment)} bp; the adapter's BbsI sites are cut away, BsaI sites for Level 1 remain.")
    return {
        "name": name, "sequence": new_seq, "length": len(new_seq),
        "insertStart": insert_start, "insertEnd": insert_end,
        "genbank": format_genbank_record(name, new_seq, features, True, definition),
    }


def _flip_location(location: str, length: int) -> str:
    """Location nach einer Drehung des Molekuels um 180 Grad (Reverse Complement der ganzen Sequenz):
    Positionen werden gespiegelt, der Strang kippt (complement() an/aus), fuzzy-Markierungen (<, >) tauschen."""
    complement = location.startswith("complement(")
    inner = location[len("complement("):-1] if complement else location
    mirror = {"<": ">", ">": "<", "": ""}

    def swap(m):
        lm, a, rm, b = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
        return f"{mirror[rm]}{length - b + 1}..{mirror[lm]}{length - a + 1}"

    inner = re.sub(r"([<>]?)(\d+)\.\.([<>]?)(\d+)", swap, inner)
    return inner if complement else f"complement({inner})"


def _rotate_built(built: dict) -> dict:
    """Dasselbe Konstrukt, um 180 Grad gedreht: Reverse Complement der gesamten Sequenz, Overhangs/BbsI-Stellen/
    Insert an gespiegelten Positionen. Fuer die Cargo Site, damit das Cargo (5' links -> 3' rechts) in seiner
    eigenen Leserichtung steht — das Konstrukt ist physisch dasselbe Molekuel, nur vom anderen Strang gelesen."""
    length = built["length"]
    seq = reverse_complement(built["sequence"])

    def flipped(item: dict) -> dict:
        loc = _flip_location(item["location"], length)
        a, b = location_span(loc)
        top = seq[a - 1:b]
        out = {**item, "location": loc, "sequence_top_strand": top}
        if "strand" in item:
            out["strand"] = "-" if loc.startswith("complement(") else "+"
        if "sequence_own_strand_5to3" in item:
            out["sequence_own_strand_5to3"] = reverse_complement(top) if loc.startswith("complement(") else top
        return out

    insert_loc = _flip_location(built["insert"]["location"], length)
    return {
        **built,
        "sequence": seq,
        "insert": {"location": insert_loc.replace("complement(", "").rstrip(")") if insert_loc.startswith("complement(") else insert_loc,
                   "sequence": reverse_complement(built["insert"]["sequence"])},
        "overhangs": [flipped(o) for o in built["overhangs"]],
        "bbsiSites": [flipped(b) for b in built["bbsiSites"]],
        "spacers": [{**sp, "location": _flip_location(sp["location"], length)} for sp in built.get("spacers", [])],
    }


def build_level0_constructs(nc: dict, cargo_label: str, cargo_antisense: str, cargo_slots: dict, nc_slots: dict,
                            fragments: list | None = None) -> list:
    """Das Level-0-Konstrukt jedes der zehn Module (Cargo Site + NC Site, Type 0.1-0.5): die Teilsequenz im
    Overhang-Adapter ihres Type-Slots (attach_adapter) und, wenn das Level-0-Backbone in der Datenbank liegt,
    das daraus per BbsI klonierte Plasmid (clone_into_level0_backbone), jeweils mit fertigem GenBank-Text.

    `isUser` = vom Nutzer eingegeben (Cargo, eigene Shell/Teile), sonst Toolkit-Teil; `isReal` = echte
    Sequenz (Nutzereingabe oder Parts-Datenbank) statt deterministischem Platzhalter.
    Orientierung wie im restlichen Design: Teile des Cargo-Moduls liegen auf dem Antisense-Strang, werden
    also als Reverse Complement eingesetzt (das Cargo ist bereits reverse-komplementiert), Teile der NC Site
    unveraendert."""
    def slot_part(cfg: dict, site: str, n: int):
        kind = cfg["kind"]
        if kind == "custom":
            return cfg["label"], cfg["seq"], True, True, "your own part", None
        if kind == "tp":
            seq, real, stock = resolve_insert("tp", nc["tp"], site, n, "TP" + nc["tp"], NOMINAL_BP["TP"],
                                              variant="c_term" if n == 1 else "n_term")
            return nc["tp"], seq, real, False, "targeting peptide (toolkit part)", stock
        if kind == "linker":
            seq, real, stock = resolve_insert("linker", cfg["id"], site, n, "LINK" + cfg["id"], cfg["bp"])
            return cfg["label"], seq, real, False, "linker (toolkit part)", stock
        if kind == "marker":
            seq, real, stock = resolve_insert("marker", cfg["id"], site, n, "MARK" + cfg["id"], cfg["bp"])
            return cfg["label"], seq, real, False, "surface marker (toolkit part)", stock
        if kind == "intein":
            seq, real, stock = resolve_insert("intein", cfg["id"], site, n, "INT" + cfg["id"], cfg["bp"])
            return cfg["label"], seq, real, False, "intein (toolkit part)", stock
        seq, real, stock = resolve_insert("ncs", "ncs", site, n, "NCS", 30, ncs_role="stop" if kind == "ncsstop" else "plain")
        return "NCS", seq, real, False, "NCS spacer (toolkit part)", stock

    if nc.get("custom"):
        shell = (nc["shell"], nc["seq"], True, True, "your own nanocompartment shell", None)
    else:
        shell_seq, shell_real, shell_stock = resolve_insert("shell", nc["shell"], "nc_site", 3, "SHELL" + nc["shell"], nc["shellBp"])
        shell = (nc["shell"], shell_seq, shell_real, False, "nanocompartment shell (toolkit part)", shell_stock)
    # Stammt das Cargo unveraendert aus der Cargo-Bibliothek (Datenbank), ist es ein Toolkit-Teil mit Lagerstatus, keine Nutzereingabe.
    preset = next((e for e in find_inserts("cargo") if e["sequence"] == reverse_complement(cargo_antisense)), None)
    cargo = (cargo_label, None, True, preset is None, "cargo gene of interest" if preset is None else "cargo (toolkit part)",
             preset.get("on_stock") if preset else None)

    backbone = next(iter(load_parts()["level0_backbones"]), None)
    if backbone and not backbone.get("sequence"):
        backbone = None

    constructs = []
    for module, slots, middle in (("cargo", cargo_slots, cargo), ("nc", nc_slots, shell)):
        for n in (1, 2, 3, 4, 5):
            label, seq, is_real, is_user, what, on_stock = middle if n == 3 else slot_part(slots[n], "cargo_site" if module == "cargo" else "nc_site", n)
            if module == "cargo":
                seq = cargo_antisense if n == 3 else reverse_complement(seq)
            adapter_id = adapter_id_for(module, n)
            built = attach_adapter(adapter_id, seq)      # Top-Strand des Level-0-Plasmids, 5' links -> 3' rechts
            antisense = module == "cargo"                # Cargo-Modul sitzt dort auf dem Antisense-Strang
            plasmid = clone_into_level0_backbone(
                built, label, backbone, antisense,
                f"{backbone['id'].split('-')[0]}_{level0_record_name(label, n, module)}") if backbone else None
            if fragments is not None:      # fuer die Level-1-Assemblierung (BsaI-Fragment dieses Teils)
                fragments.append({"module": module, "slot": n, "label": label, "type": f"Type 0.{n}", "what": what,
                                  "isReal": is_real, "isUser": is_user, "fragment": level1_fragment(built),
                                  "insertSequence": built["insert"]["sequence"]})
            # Anzeige/Export des Konstrukts: Cargo Site um 180 Grad gedreht, damit das Cargo in seiner eigenen
            # Leserichtung steht (5' links -> 3' rechts); NC Site unveraendert.
            shown = _rotate_built(built) if antisense else built
            construct_features = [_feat("misc_feature", b["location"], "BbsI rec site") for b in shown["bbsiSites"]]
            construct_features += [_feat("overhang", o["location"], o["label"], f"{o['role']} · top strand {o['sequence_top_strand']}")
                                   for o in shown["overhangs"]]
            orientation = ("antisense strand (cargo module) — shown 5'->3' left to right, rotated 180° vs. the Level 0 plasmid top strand"
                           if antisense else "sense strand — as entered")
            construct_features += [_feat("misc_feature", sp["location"], "Frame spacer", sp["note"]) for sp in shown["spacers"]]
            construct_features.append(_feat("CDS", shown["insert"]["location"], label,
                                            f"Type 0.{n} · {what} · {orientation} · adapter {adapter_id}"))
            primers = design_level0_primers(shown, label, n, module) if is_real else {
                "possible": False, "reason": "No real sequence in the parts database yet — primers can only be designed for a real sequence."}
            oligos = None
            if is_real and not primers["possible"]:
                oligos = design_level0_oligos(built, label, n, module)
            product_features = list(construct_features)
            if primers["possible"]:
                primers["genbank"] = pcr_product_genbank(shown, primers, label, n, module, adapter_id, product_features)
                i_start, i_end = location_span(shown["insert"]["location"])
                for key, loc in (("forward", f"{i_start}..{i_start + primers['forward']['annealLength'] - 1}"),
                                 ("reverse", f"complement({i_end - primers['reverse']['annealLength'] + 1}..{i_end})")):
                    construct_features.append(_feat("primer_bind", loc, primers[key]["name"],
                                                    f"annealing part of {primers[key]['name']} (Tm {primers[key]['tm']} °C)"))
            construct_features.sort(key=lambda f: location_span(f["location"])[0])
            definition = (f"Level 0 construct for the {'cargo' if module == 'cargo' else 'nanocompartment'} site: {label} in adapter "
                          f"{adapter_id} (BbsI). Sequence 5'->3' left to right, {'antisense strand (cargo module); shown rotated 180 degrees relative to the Level 0 plasmid top strand' if antisense else 'sense strand'}.")
            if not is_real:
                definition += " PLACEHOLDER insert — the real sequence is not in the parts database yet."
            record_name = level0_record_name(label, n, module)
            constructs.append({
                "label": label, "what": what, "module": "cargo_site" if module == "cargo" else "nc_site",
                "slot": n, "type": f"Type 0.{n}", "orientation": orientation,
                "strand": "antisense" if antisense else "sense", "rotated": antisense,
                "plasmidStrand": "antisense" if antisense else "sense",
                "isUser": is_user, "isReal": is_real,
                "adapter": built["adapter"], "usedForModules": built["usedForModules"],
                "sequence": shown["sequence"], "length": shown["length"], "insert": shown["insert"],
                "overhangs": shown["overhangs"], "bbsiSites": shown["bbsiSites"],
                "primers": primers, "oligos": oligos, "onStock": None if is_user else on_stock,
                "genbank": format_genbank_record(record_name, shown["sequence"], construct_features, False, definition),
                "plasmid": plasmid,
            })
    return constructs


def build_genbank(design: dict) -> str:
    """Gesamt-GenBank-Export: die Level-0-Konstrukte der Nutzereingaben (mit PCR-Produkt/Primern), die drei Level-1-Inserts
    und das fertige Level-2-Plasmid (mit den echten Annotationen von pESC-HIS) — siehe assembly.py."""
    records: list[str] = []

    def add_record(name: str, sequence: str, features: list[dict] | None = None,
                    circular: bool = False, definition: str = ""):
        records.append(format_genbank_record(name, sequence, features, circular, definition))

    # Level-0-Konstrukte der Nutzereingaben (Cargo, eigene Shell/Teile): Teilsequenz im Type-Adapter mit allen Annotationen
    # (BbsI-Stellen, Overhangs, Frame-Spacer, Insert), plus ggf. das PCR-Produkt mit den Primern.
    for c in (c for c in design.get("level0Constructs", []) if c["isUser"]):
        records.append(c["genbank"])
        if c["primers"]["possible"]:
            records.append(c["primers"]["genbank"])

    # Level 1 (BsaI) und Level 2 (BbsI): die tatsaechlichen Assemblies samt Overhangs (siehe assembly.py).
    for module in design.get("level1Constructs", []):
        records.append(module["shown"]["genbank"] if module.get("shown") else module["genbank"])
    level2 = design.get("level2Construct")
    if level2:
        records.append(level2["plasmid"]["genbank"] if level2["plasmid"] else level2["genbank"])

    return "\n\n".join(records)
