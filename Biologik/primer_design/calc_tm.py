#!/usr/bin/env python3
from __future__ import annotations

import primer3

from .evaluate_primer import evaluate_primer
from .get_primer import resolve_sequence, slice_primers


class BalancingError(Exception):
    """Raised when primers cannot be balanced to meet Tm constraints at a given length."""


def count_bases(seq: str) -> dict:
    seq = seq.upper()
    return {
        "A": seq.count("A"),
        "T": seq.count("T"),
        "G": seq.count("G"),
        "C": seq.count("C"),
    }


def tm_wallace(seq: str) -> float:
    counts = count_bases(seq)
    return 2 * (counts["A"] + counts["T"]) + 4 * (counts["G"] + counts["C"])


def shorten_one_base(primer: str) -> str:
    return primer[:-1]


def balance_primers(
    primer1: str,
    primer2: str,
    min_len: int = 18,
    max_diff: float = 2.0,
    max_tm: float = 72.0,
) -> tuple:
    """Shorten primers from the 3' end until both are below max_tm and their Tm difference is within max_diff."""
    p1 = primer1.upper()
    p2 = primer2.upper()

    while True:
        tm1 = primer3.bindings.calc_tm(p1)
        tm2 = primer3.bindings.calc_tm(p2)

        if tm1 > max_tm:
            if len(p1) <= min_len:
                raise BalancingError(f"Primer 1 exceeds {max_tm}°C even at minimum length {min_len}")
            p1 = shorten_one_base(p1)
            continue

        if tm2 > max_tm:
            if len(p2) <= min_len:
                raise BalancingError(f"Primer 2 exceeds {max_tm}°C even at minimum length {min_len}")
            p2 = shorten_one_base(p2)
            continue

        if abs(tm1 - tm2) <= max_diff:
            return p1, p2, tm1, tm2

        if tm1 > tm2:
            if len(p1) <= min_len:
                raise BalancingError(f"Primer 1 cannot be shortened below {min_len} bp")
            p1 = shorten_one_base(p1)
        else:
            if len(p2) <= min_len:
                raise BalancingError(f"Primer 2 cannot be shortened below {min_len} bp")
            p2 = shorten_one_base(p2)


def find_best_primers(
    fasta_file: str | None = None,
    min_len: int = 18,
    max_len: int = 25,
    *,
    sequence: str | None = None,
):
    """Beste Primerlänge suchen — akzeptiert FASTA-Datei ODER Sequenz-String.

    Die Sequenz wird einmal aufgelöst und danach nur noch geschnitten (vorher
    wurde die FASTA-Datei in jedem Schleifendurchlauf neu von der Platte
    gelesen). Ergebnis identisch.
    """
    seq = resolve_sequence(sequence=sequence, fasta_file=fasta_file)

    best_result = None
    best_issues_count = float('inf')

    for primer_len in range(max_len, min_len - 1, -1):
        try:
            sense, antisense_rc = slice_primers(seq, primer_length=primer_len)
            primer_fw, primer_rv, tm_fw, tm_rv = balance_primers(sense, antisense_rc)
            result = evaluate_primer(primer_fw, primer_rv)

            issues_count = len(result["issues"])
            if issues_count < best_issues_count:
                best_issues_count = issues_count
                best_result = {
                    "primer_fw": primer_fw,
                    "primer_rv": primer_rv,
                    "tm_fw": tm_fw,
                    "tm_rv": tm_rv,
                    "q5_annealing_temp": q5_annealing_temp(tm_fw, tm_rv),
                    "evaluation": result,
                    "primer_len": primer_len,
                    "issues_count": issues_count,
                }

            if result["valid"]:
                break

        except BalancingError:
            continue

    return best_result


def q5_annealing_temp(tm_fwd: float, tm_rev: float) -> float:
    tm = min(tm_fwd, tm_rev)
    if tm >= 70:
        offset = 2
    elif tm >= 65:
        offset = 3
    elif tm >= 60:
        offset = 4
    else:
        offset = 5
    return tm - offset
