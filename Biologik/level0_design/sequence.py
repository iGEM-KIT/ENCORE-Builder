from __future__ import annotations

"""Hilfsfunktionen für Cargo-Validierung."""

# In diesem Ordner wird die vom Benutzer frei eingegebene Cargo-Sequenzen (Gene of Interest) verarbeitet.
# Es sind kleine, unabhängige Funktionen aufgeführt, auf denen die Validierung der Cargo-Sequenzen aufbaut. 
# Mit der Validierung der Cargo-Sequenz wird geprüft, ob eine vom User eingegebene Cargo-Sequenz eine gültige
# und ausreichend lange DNA-Sequenz ist und lang genug ist und kein Stopcodon enthält.

import re

from .data import STOP_CODONS

# Wenn Uracil (mRNA) in Cargo-Sequenz enthalten ist, zu DNA umschreiben und dem USser als Anmerkung/Info anzeigen.
COMPLEMENT = {"A": "T", "T": "A", "G": "C", "C": "G"}

# Definition von Funktionen mit def
# DNA-Sequenz "sequence" vom Dateityp str wird als Parameter/ Input übergeben -> Platzhalter für die vom User eingegebene Sequenz.
# Die Funktionen geben als Output entweder den Dateityp str oder int zurück.
# str steht für den Dateitp String, also eine Text bzw. eine Zeichenkette, z.B. 'GCT'
# int steht für den Dateityp Integer, also eine ganze Zahl ohne Nachkommastellen, z.B. '42'


 # Prüfen, ob nur gültige Basen (A,T,G,C,) verwendet werden.
def clean_seq(sequence: str) -> str:
    # re.sub() ersetzt alle Zeichen, die nicht A, T, G oder C sind, durch nichts.
    # Wenn beim Code kopieren noch zusätzliche Zeichen mitkopiert wurden.
    return re.sub(r"[^ATGC]", "", (sequence or "").upper())
         

def gc_content(sequence: str) -> int:
    # Zählt GC-Gehalt: die drei Wasserstoffbrücken der G–C-Paarung ist Hauptfaktor für die Stabilität,
    # relevant für Primer-Schmelztemperaturen, die Wahl der Fusion Sites und die Synthetisierbarkeit einer CDS.
    # Wenn die Sequenz leer ist, wird direkt 0 zurückgegeben.
    # Ist Auswählung des GC-Gehalts an dieser Stelle redundant? Wird unten nochmal gezählt.
    if not sequence:
        return 0
    # Die Schleife mit for geht jede Base der Sequenz durch und zählt die G/C-Basen
    return round((sum(1 for base in sequence if base in "GC") / len(sequence)) * 100)


def reverse_complement(sequence: str) -> str:
    # reversed(...) dreht die Reihenfolge um, und die Komplement-Tabelle ersetzt jede Base
    # Um Leserichtung bei Bildung des Gegenstrangs beizubehalten, muss Sequenz rückwärts gelesen werden (reverse) 
    # Komplement-Tabelle ist ein Dictionary, das jede Base auf ihre Basenpaarungspartnerin abbildet:
    return "".join(COMPLEMENT.get(base, "N") for base in reversed(sequence))


def wallace_tm(sequence: str) -> int:
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


# Wenn ATG gefunden, alles vor ATG löschen und User mit Anzeige informieren.


def validate_cargo(raw: str, min_bp: int = 30) -> dict:
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
