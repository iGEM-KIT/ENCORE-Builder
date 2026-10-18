"""Helper functions for cargo validation."""

from __future__ import annotations


# This module processes the cargo sequences (gene of interest) freely entered by the user.
# It lists small, independent functions on which the validation of the cargo sequences builds.
# The validation of the cargo sequence checks whether a cargo sequence entered by the user is a valid
# DNA sequence of sufficient length and contains no stop codon.

import re

from .data import STOP_CODONS

# If uracil (mRNA) is contained in the cargo sequence, convert it to DNA and show the user a note/info.
COMPLEMENT = {"A": "T", "T": "A", "G": "C", "C": "G"}

# Definition of functions with def
# The DNA sequence "sequence" of type str is passed as a parameter/input -> placeholder for the sequence entered by the user.
# The functions return either the type str or int as output.
# str stands for the type string, i.e. a text or character string, e.g. 'GCT'
# int stands for the type integer, i.e. a whole number without decimals, e.g. '42'


 # Check whether only valid bases (A,T,G,C) are used.
def clean_seq(sequence: str) -> str:
    # re.sub() replaces all characters that are not A, T, G or C by nothing.
    # If additional characters were copied along when copying the code.
    return re.sub(r"[^ATGC]", "", (sequence or "").upper())
         

AMINO_ACIDS = "ACDEFGHIKLMNPQRSTVWY"


def _without_fasta_header(raw: str) -> str:
    """Upper case, without FASTA header lines (">name")."""
    return re.sub(r"^>.*$", "", (raw or "").upper(), flags=re.M)


def is_protein(raw: str) -> bool:
    """Amino acid instead of DNA? A DNA consists (apart from spaces/digits) almost only of A/T/G/C (also U/N); a protein has
        only about a quarter of such letters. From 90 % A/C/G/T/U/N on the input counts as DNA. FASTA header lines (">...") do not count."""
    letters = re.sub(r"[^A-Z*]", "", _without_fasta_header(raw))
    if not letters:
        return False
    return sum(1 for c in letters if c in "ACGTUN") / len(letters) < 0.9


def clean_protein(raw: str) -> str:
    """Only the 20 amino acids (and an asterisk for a stop codon) remain; FASTA header lines, spaces and digits are dropped."""
    return re.sub(rf"[^{AMINO_ACIDS}*]", "", _without_fasta_header(raw))


def gc_content(sequence: str) -> int:
    # Counts the GC content: the three hydrogen bonds of the G-C pairing are the main factor for stability,
    # relevant for primer melting temperatures, the choice of fusion sites and the synthesizability of a CDS.
    # If the sequence is empty, 0 is returned directly.
    # Is counting the GC content at this point redundant? It is counted again below.
    if not sequence:
        return 0
    # The for loop goes through every base of the sequence and counts the G/C bases
    return round((sum(1 for base in sequence if base in "GC") / len(sequence)) * 100)


def reverse_complement(sequence: str) -> str:
    # reversed(...) reverses the order, and the complement table replaces every base
    # To keep the reading direction when forming the opposite strand, the sequence has to be read backwards (reverse)
    # The complement table is a dictionary that maps every base to its base pairing partner:
    return "".join(COMPLEMENT.get(base, "N") for base in reversed(sequence))


def wallace_tm(sequence: str) -> int:
    # sum(...) counts A/T and G/C bases. The formula roughly calculates the melting temperature.
    at = sum(1 for base in sequence if base in "AT")
    gc = sum(1 for base in sequence if base in "GC")
    return 2 * at + 4 * gc


def find_internal_stops(sequence: str):
    # An empty list is created as a container for results.
    hits = []
    # A for loop runs over the sequence in steps of 3 bases.
    for index in range(0, len(sequence) - 2, 3):
        codon = sequence[index:index + 3]
        if codon in STOP_CODONS:
            hits.append({"pos": index, "codon": codon})
    return hits


def ends_with_stop(sequence: str):
    if len(sequence) >= 3 and sequence[-3:] in STOP_CODONS:
        return sequence[-3:]
    return None


# If ATG is found, delete everything before ATG and inform the user with a message.


def validate_cargo(raw: str, min_bp: int = 30, kind: str = "cargo") -> dict:
    # ``kind`` is "cargo" (default), "shell" for an own nanocompartment shell or "part" for an own sequence in a slot;
    # only the cargo has a minimum length. A start codon is optional (the builder adds ATG where the ORF begins).
    # The input may be DNA (CDS) or an amino acid sequence (``isProtein``); a protein is translated into DNA when building, using the
    # codon usage of S. cerevisiae (codon.py), ``length`` is then the length of this DNA (3 per amino acid).
    if is_protein(raw):
        return _validate_protein(raw, min_bp, kind)
    # clean_seq() makes the input usable for further analysis.
    clean = clean_seq(raw)
    invalid_chars = len(re.sub(r"[ATGC\s]", "", (raw or "").upper()))
    # A stop codon at the end is taken off: the builder adds the stop codon itself where the ORF ends (constructs.py).
    trailing_stop = ends_with_stop(clean)
    if trailing_stop:
        clean = clean[:-3]
    length = len(clean)
    not_multiple_of_three = length % 3 != 0
    internal_stops = find_internal_stops(clean) if length >= 3 else []

    errors = []
    warnings = []

    if length == 0:
        errors.append("No valid A/T/G/C sequence provided.")
    else:
        # The minimum length only applies to the cargo (primers are designed for it); shell and
        # own modules are ordered as synthesis and may be arbitrarily short.
        if kind == "cargo" and length < min_bp:
            errors.append(f"Sequence too short ({length} bp, need at least {min_bp} bp).")
        if not_multiple_of_three:
            warnings.append("Length is not a multiple of 3; check the reading frame.")
        if internal_stops:
            first = internal_stops[0]
            warnings.append(f"Possible in-frame stop codon at position {first['pos'] + 1} ({first['codon']}).")
        if invalid_chars > 0:
            warnings.append(f"{invalid_chars} invalid character(s) were ignored.")
    if trailing_stop or clean.startswith("ATG"):
        warnings.append(_stop_message(trailing_stop, clean.startswith("ATG")))

    return {
        "clean": clean,
        "length": length,
        "aa": length // 3,
        "gc": gc_content(clean),
        "invalidChars": invalid_chars,
        "notMultipleOfThree": not_multiple_of_three,
        "trailingStop": trailing_stop,
        "internalStops": internal_stops,
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "isProtein": False,
    }


def _stop_message(stop: str | None, has_start: bool = False) -> str:
    # Present tense, the builder acts: it takes the stop codon off and does not double a start codon (constructs.py: _add_start_stop).
    parts = ([f"removes the stop codon at the end ({stop})"] if stop else []) + (["does not double the start codon (ATG)"] if has_start else [])
    return f"The builder {' and '.join(parts)}: it adds start and stop codon itself where the ORF begins and ends."


def _validate_protein(raw: str, min_bp: int, kind: str) -> dict:
    """Like validate_cargo, for an amino acid sequence: ``clean`` is the amino acid sequence, ``length`` the length of the DNA after
        back-translation. A trailing asterisk is a stop codon (taken off with a warning, as for DNA), an asterisk in the middle is a warning."""
    clean = clean_protein(raw)
    invalid_chars = len(re.sub(rf"[{AMINO_ACIDS}*\s]", "", _without_fasta_header(raw)))
    trailing_stop = "*" if clean.endswith("*") else None
    residues = clean[:-1] if trailing_stop else clean
    clean = residues
    length = 3 * len(residues)
    internal_stops = [{"pos": i, "codon": "*"} for i, c in enumerate(residues) if c == "*"]

    errors, warnings = [], []
    if not residues:
        errors.append("No valid amino acid sequence provided.")
    else:
        if kind == "cargo" and length < min_bp:
            errors.append(f"Sequence too short ({len(residues)} aa, need at least {min_bp // 3} aa).")
        if internal_stops:
            warnings.append(f"Stop (*) at residue {internal_stops[0]['pos'] + 1}: translation would end there.")
        if invalid_chars > 0:
            warnings.append(f"{invalid_chars} invalid character(s) were ignored.")
    if trailing_stop:
        warnings.append(_stop_message("*"))
    return {
        "clean": clean, "length": length, "aa": len(residues), "gc": None, "invalidChars": invalid_chars,
        "notMultipleOfThree": False, "trailingStop": trailing_stop, "internalStops": internal_stops,
        "ok": not errors, "errors": errors, "warnings": warnings, "isProtein": True,
    }


# An own promoter is a DNA part of the Level 1 promoter module: it is made by PCR (primers with the BsaI overhangs, see
# primers.design_promoter_primers), so it needs the length of a PCR product, and it must not contain a site of the two enzymes of the assembly.
MIN_PROMOTER_BP = 150
MAX_PROMOTER_BP = 3000


def validate_promoter(raw: str) -> dict:
    """Check an own promoter sequence (DNA only). Same answer shape as validate_cargo(), plus `sites`.

        Errors (the construct cannot be built): not DNA, too short/long, a BsaI or BbsI site (the Level 1 and Level 2 assembly would cut the
        promoter). Warnings: sites of the iGEM standards (SapI, EcoRI, XbaI, SpeI, PstI, NotI): a promoter cannot be recoded like a CDS, so
        they stay; invalid characters that were ignored."""
    from .codon import find_forbidden
    text = raw or ""
    clean = clean_seq(text.upper().replace("U", "T"))
    length = len(clean)
    invalid_chars = len(re.sub(r"[ATGC\s]", "", text.upper().replace("U", "T")))
    errors, warnings = [], []
    protein = is_protein(text)
    if protein:
        errors.append("A promoter is a DNA sequence: amino acids cannot be used here.")
    elif length == 0:
        errors.append("No valid A/T/G/C sequence provided.")
    else:
        if length < MIN_PROMOTER_BP:
            errors.append(f"Sequence too short ({length} bp, need at least {MIN_PROMOTER_BP} bp).")
        if length > MAX_PROMOTER_BP:
            errors.append(f"Sequence too long ({length} bp, at most {MAX_PROMOTER_BP} bp).")
        if invalid_chars > 0:
            warnings.append(f"{invalid_chars} invalid character(s) were ignored.")
    hits = find_forbidden(clean) if clean and not protein else []
    for enzyme in dict.fromkeys(h["enzyme"] for h in hits):
        found = [h for h in hits if h["enzyme"] == enzyme]
        where = ", ".join(str(h["pos"] + 1) for h in found[:4]) + (" ..." if len(found) > 4 else "")
        if enzyme in ("BsaI", "BbsI"):
            errors.append(f"{enzyme} site ({found[0]['site']}) at position {where}: the assembly would cut the promoter. "
                          f"Remove it with a point mutation.")
        else:
            warnings.append(f"{enzyme} site ({found[0]['site']}) at position {where}: allowed for the assembly, but the iGEM standards forbid it in a part.")
    return {
        "clean": clean, "length": length, "aa": length // 3, "gc": gc_content(clean), "invalidChars": invalid_chars,
        "notMultipleOfThree": False, "trailingStop": None, "internalStops": [],
        "sites": [{"enzyme": h["enzyme"], "pos": h["pos"] + 1, "site": h["site"]} for h in hits],
        "ok": not errors, "errors": errors, "warnings": warnings, "isProtein": False, "isPromoter": True,
    }
