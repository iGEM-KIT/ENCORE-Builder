"""PCR primers: the cargo primer pair for Level 1 and the Level 0 primers for own sequences, with the PCR product as GenBank."""

from __future__ import annotations

from .codon import FORBIDDEN_SITES
from .data import BSAI_PRIMER_PREFIX
from .genbank_writer import (format_genbank_record, level0_record_name, location_span, make_feature as _feat,
                             shift_location)
from .sequence import reverse_complement, wallace_tm


def _wallace_anneal(sequence: str):
    """Annealing parts (forward, reverse) by the Wallace rule (2 °C per A/T, 4 °C per G/C).

        Fallback when primer3 is not installed or finds no pair. Good enough
        for the preview, not for ordering. Returns (anneal_f, anneal_r, balanced).

    """
    # len_f and len_r are the annealing lengths of the primers. They are adjusted so that the Tm values fit.
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
            # stop, because no sensible adjustment is possible any more
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
    """Real nearest-neighbour thermodynamics from ``Biologik.primer_design``.

        The import is local on purpose: ``level0_design`` should stay usable without primer3,
        so the dependency is only pulled in when this is called.

        The dimer/hairpin evaluation runs only on the ANNEALING region, not
        on the finished oligo. Reason: ``BSAI_PRIMER_PREFIX`` ends in a
        literal "N", and primer3 rejects non-ACGT bases
        ("Sequence contains non-ACGT base 'N'"). As soon as the spacer is fixed to a
        concrete base, the full primer should be checked here
        (via ``ext_fw`` / ``ext_rv`` in ``design_primers``); the overhang
        measurably changes the secondary structure.

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
    """Builds the two primer entries from annealing part + BsaI prefix + overhang.

        The overhangs come unchanged from the calling code (currently
        CARGO_L1_FLANK). They are NOT identical to the extensions in
        ``primer_design/add_extensions.py`` (type0.3 appends TTCT, i.e. the
        Type 3 overhang). Which variant describes the real toolbox
        still has to be checked against the lab. Nothing is decided here
        on purpose: the thermodynamics were swapped, the
        biology was not.

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
    """Primer pair for the cargo. Uses primer3, otherwise falls back to Wallace.

        ``use_primer3=False`` forces the fallback (for tests and for a plain
        preview without primer3 installed).

    """
    if use_primer3:
        try:
            return _primer3_primer_pair(sequence, oh_f, oh_r)
        except ImportError:
            pass  # primer3-py not installed -> Wallace
        except ValueError:
            pass  # no valid pair found -> Wallace

    return _wallace_primer_pair(sequence, oh_f, oh_r)


# 5' clamp in front of the BbsI recognition site: restriction enzymes cut badly at the end of a PCR product
# if the recognition site lies right at the edge.
PCR_CLAMP = "TTTT"


# Parts (own ones as well as those from the database) below this length are ordered as annealed oligo pairs; from this length on
# there are primers (PCR) for own sequences and the DNA order for toolbox parts (finished fragments only exist from ~125 bp).
MIN_PCR_INSERT_BP = 150


def design_level0_primers(shown: dict, label: str, slot: int, module: str):
    """PCR primers that make an existing part sequence (`shown["insert"]`, 5'->3' in the construct) Level 0 compatible:
        5' overhang = clamp + the whole adapter flank before/after the insert (BbsI site, Level 0/
        Level 1/where applicable Level 2 overhangs, BsaI site), 3' part = annealing to the insert (primer3, otherwise Wallace).
        The PCR product equals `shown["sequence"]` plus one clamp on each side, so it can be cloned directly with BbsI
        into the Level 0 backbone. Returns `{"possible": False, "reason": ...}` if the insert
        is too short for PCR."""
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
        pass  # primer3 missing or no pair -> Wallace
    if result:
        anneal_f, anneal_r = result["annealFw"], result["annealRv"]
        tm_f, tm_r, method = round(result["tmFw"], 1), round(result["tmRv"], 1), "primer3-nn"
        q5 = round(result["q5AnnealingTemp"], 1)
        issues = list(result["issues"])
        structure = _structure_checks(result["evaluation"])
    else:
        anneal_f, anneal_r, balanced = _wallace_anneal(insert)
        tm_f, tm_r, method, q5 = wallace_tm(anneal_f), wallace_tm(anneal_r), "wallace", None
        issues = [] if balanced else [_WALLACE_HINT]
        structure = None

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
        "structure": structure,
        "internalSites": sites,
    }


def _structure_checks(evaluation: dict) -> dict:
    """Self-fold (hairpin), self-dimer (homodimer) and primer-primer dimer (heterodimer) of the finished primers, from the
    primer3 evaluation of the complete oligos (clamp + adapter flank + annealing part). ΔG in kcal/mol, `ok` = below the thresholds
    of Biologik/primer_design/evaluate_primer.py."""
    def kcal(dg) -> float:
        return round(dg / 1000, 1)

    return {
        "hairpin": {"forward": {"deltaG": kcal(evaluation["hairpin_fw_dG"]), "ok": evaluation["hairpin_fw_ok"]},
                    "reverse": {"deltaG": kcal(evaluation["hairpin_rv_dG"]), "ok": evaluation["hairpin_rv_ok"]}},
        "selfDimer": {"forward": {"deltaG": kcal(evaluation["self_fw_dG"]), "ok": evaluation["self_fw_ok"]},
                      "reverse": {"deltaG": kcal(evaluation["self_rv_dG"]), "ok": evaluation["self_rv_ok"]}},
        "heteroDimer": {"deltaG": kcal(evaluation["hetero_dimer_dG"]), "ok": evaluation["hetero_ok"]},
    }


def pcr_product_genbank(shown: dict, primers: dict, label: str, slot: int, module: str, adapter_id: str, features: list) -> str:
    """GenBank record of the PCR product (clamp + construct + clamp, linear) with both primers as
        `primer_bind` over their full length (clamp + adapter flank + annealing part). `features` are the
        construct features (BbsI sites, overhangs, insert) in construct coordinates; they are shifted by the clamp."""
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
