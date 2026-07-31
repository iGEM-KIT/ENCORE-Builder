from __future__ import annotations

"""Hilfsfunktionen für DNA-Sequenzen und Cargo-Validierung."""

import re

from .data import STOP_CODONS

COMPLEMENT = {"A": "T", "T": "A", "G": "C", "C": "G"}


def clean_seq(sequence: str) -> str:
    # Eine Funktion definiert einen wiederverwendbaren Block aus Anweisungen.
    # re.sub() ersetzt alle Zeichen, die nicht A, T, G oder C sind, durch nichts.
    return re.sub(r"[^ATGC]", "", (sequence or "").upper())


def gc_content(sequence: str) -> int:
    # Eine Funktion kann mit if entscheiden, welchen Pfad sie nimmt.
    # Wenn die Sequenz leer ist, wird direkt 0 zurückgegeben.
    if not sequence:
        return 0
    # Eine Schleife mit for geht jede Base der Sequenz durch und zählt die G/C-Basen.
    return round((sum(1 for base in sequence if base in "GC") / len(sequence)) * 100)


def reverse_complement(sequence: str) -> str:
    # Eine Funktion kann den Input verarbeiten und einen neuen Wert zurückgeben.
    # reversed(...) dreht die Reihenfolge um, und die Komplement-Tabelle ersetzt jede Base.
    return "".join(COMPLEMENT.get(base, "N") for base in reversed(sequence))


def wallace_tm(sequence: str) -> int:
    # Eine Funktion kann mehrere Zwischenschritte ausführen, bevor sie ein Ergebnis liefert.
    # sum(...) zählt A/T- und G/C-Basen. Die Formel berechnet die Schmelztemperatur grob.
    at = sum(1 for base in sequence if base in "AT")
    gc = sum(1 for base in sequence if base in "GC")
    return 2 * at + 4 * gc


def find_internal_stops(sequence: str):
    # Eine leere Liste wird als Sammelbehälter für Ergebnisse angelegt.
    hits = []
    # Eine for-Schleife läuft über die Sequenz in Schritten von 3 Basen.
    for index in range(0, len(sequence) - 2, 3):
        codon = sequence[index:index + 3]
        if codon in STOP_CODONS:
            hits.append({"pos": index, "codon": codon})
    return hits


def ends_with_stop(sequence: str):
    if len(sequence) >= 3 and sequence[-3:] in STOP_CODONS:
        return sequence[-3:]
    return None


def validate_cargo(raw: str, min_bp: int = 30) -> dict:
    # Funktionen können Parameter entgegennehmen, hier z. B. die Sequenz und Mindestlänge.
    # clean_seq() macht die Eingabe für die weitere Analyse brauchbar.
    clean = clean_seq(raw)
    length = len(clean)
    invalid_chars = len(re.sub(r"[ATGC\s]", "", (raw or "").upper()))
    not_multiple_of_three = length % 3 != 0
    trailing_stop = ends_with_stop(clean)
    internal_stops = find_internal_stops(clean[:-3]) if length >= 3 else []

    errors = []
    warnings = []

    if length == 0:
        errors.append("No valid A/T/G/C sequence provided.")
    else:
        if length < min_bp:
            errors.append(f"Sequence too short ({length} bp, need at least {min_bp} bp).")
        if trailing_stop:
            errors.append(
                f"Stop codon at the end ({trailing_stop}). Remove it — otherwise the targeting peptide is not attached and the cargo is not encapsulated."
            )
        if not_multiple_of_three:
            warnings.append("Length is not a multiple of 3 — check the reading frame.")
        if internal_stops:
            first = internal_stops[0]
            warnings.append(f"Possible in-frame stop codon at position {first['pos'] + 1} ({first['codon']}).")
        if invalid_chars > 0:
            warnings.append(f"{invalid_chars} invalid character(s) were ignored.")

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
    }
