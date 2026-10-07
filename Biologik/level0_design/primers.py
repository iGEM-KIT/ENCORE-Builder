"""PCR-Primer: das Cargo-Primerpaar fuer Level 1 und die Level-0-Primer fuer eigene Sequenzen samt PCR-Produkt als GenBank."""

from __future__ import annotations

from .codon import FORBIDDEN_SITES
from .data import BSAI_PRIMER_PREFIX
from .genbank_writer import (format_genbank_record, level0_record_name, location_span, make_feature as _feat,
                             shift_location)
from .sequence import reverse_complement, wallace_tm


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
    "Note: the automatic adjustment of the primer lengths could not bring the melting temperatures within 5 °C of each other. "
    "Check the primers by hand or adjust the sequence or the annealing lengths."
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


# Teile (eigene wie aus der Datenbank) unter dieser Laenge werden als annealte Oligo-Paare bestellt, ab dieser Laenge gibt
# es fuer eigene Sequenzen Primer (PCR) bzw. fuer Toolbox-Teile die DNA-Bestellung (fertige Fragmente gibt es erst ab ~125 bp).
MIN_PCR_INSERT_BP = 150


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
                "reason": f"Insert is only {len(insert)} bp: below {MIN_PCR_INSERT_BP} bp parts are ordered as two annealed oligos "
                          f"carrying the same overhangs instead of PCR."}
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
    sites = [f"{enzyme} site ({site})" for enzyme, pair in FORBIDDEN_SITES.items()
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
