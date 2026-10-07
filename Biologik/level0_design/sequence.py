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
         

AMINO_ACIDS = "ACDEFGHIKLMNPQRSTVWY"


def _without_fasta_header(raw: str) -> str:
    """Grossgeschrieben, ohne FASTA-Kopfzeilen (">name")."""
    return re.sub(r"^>.*$", "", (raw or "").upper(), flags=re.M)


def is_protein(raw: str) -> bool:
    """Aminosaeure statt DNA? Eine DNA besteht (bis auf Leerzeichen/Ziffern) fast nur aus A/T/G/C (auch U/N); ein Protein hat
    nur etwa ein Viertel solche Buchstaben. Ab 90 % A/C/G/T/U/N gilt die Eingabe als DNA. FASTA-Kopfzeilen (">...") zaehlen nicht."""
    letters = re.sub(r"[^A-Z*]", "", _without_fasta_header(raw))
    if not letters:
        return False
    return sum(1 for c in letters if c in "ACGTUN") / len(letters) < 0.9


def clean_protein(raw: str) -> str:
    """Nur die 20 Aminosaeuren (und ein Stern fuer ein Stopcodon) bleiben; FASTA-Kopfzeilen, Leerzeichen und Ziffern fallen weg."""
    return re.sub(rf"[^{AMINO_ACIDS}*]", "", _without_fasta_header(raw))


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


def validate_cargo(raw: str, min_bp: int = 30, kind: str = "cargo") -> dict:
    # ``kind`` waehlt nur den Wortlaut der Stopcodon-Meldung: "cargo" (Standard), "shell" fuer eine
    # eigene Nanocompartment-Shell oder "part" fuer eine eigene Sequenz in einem Slot. Die Regeln sind identisch.
    # Die Eingabe darf DNA (CDS) oder eine Aminosaeuresequenz sein (``isProtein``); ein Protein wird beim Bauen mit der
    # Codon-Nutzung von S. cerevisiae in DNA uebersetzt (codon.py), ``length`` ist dann die Laenge dieser DNA (3 pro Aminosaeure).
    if is_protein(raw):
        return _validate_protein(raw, min_bp, kind)
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
        # Die Mindestlaenge gilt nur fuer das Cargo (dafuer werden Primer designt); Shell und
        # eigene Module werden als Synthese bestellt und duerfen beliebig kurz sein.
        if kind == "cargo" and length < min_bp:
            errors.append(f"Sequence too short ({length} bp, need at least {min_bp} bp).")
        if trailing_stop:
            errors.append(_stop_message(trailing_stop, kind))
        if not_multiple_of_three:
            warnings.append("Length is not a multiple of 3; check the reading frame.")
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
        "isProtein": False,
    }


def _stop_message(stop: str, kind: str) -> str:
    where = {"shell": "the construct adds its own stop codon right after the shell.",
             "part": "the construct places its own stop codon at the end of the nanocompartment site."}.get(
        kind, "otherwise the targeting peptide is not attached and the cargo is not encapsulated.")
    return f"Stop codon at the end ({stop}). Remove it: {where}"


def _validate_protein(raw: str, min_bp: int, kind: str) -> dict:
    """Wie validate_cargo, fuer eine Aminosaeuresequenz: ``clean`` ist die Aminosaeurefolge, ``length`` die Laenge der DNA nach der
    Rueckuebersetzung. Ein Stern am Ende ist ein Stopcodon (Fehler wie bei DNA), ein Stern mitten drin eine Warnung."""
    clean = clean_protein(raw)
    invalid_chars = len(re.sub(rf"[{AMINO_ACIDS}*\s]", "", _without_fasta_header(raw)))
    trailing_stop = "*" if clean.endswith("*") else None
    residues = clean[:-1] if trailing_stop else clean
    length = 3 * len(residues)
    internal_stops = [{"pos": i, "codon": "*"} for i, c in enumerate(residues) if c == "*"]

    errors, warnings = [], []
    if not residues:
        errors.append("No valid amino acid sequence provided.")
    else:
        if kind == "cargo" and length < min_bp:
            errors.append(f"Sequence too short ({len(residues)} aa, need at least {min_bp // 3} aa).")
        if trailing_stop:
            errors.append(_stop_message("*", kind))
        if internal_stops:
            warnings.append(f"Stop (*) at residue {internal_stops[0]['pos'] + 1}: translation would end there.")
        if invalid_chars > 0:
            warnings.append(f"{invalid_chars} invalid character(s) were ignored.")
    return {
        "clean": clean, "length": length, "aa": len(residues), "gc": None, "invalidChars": invalid_chars,
        "notMultipleOfThree": False, "trailingStop": trailing_stop, "internalStops": internal_stops,
        "ok": not errors, "errors": errors, "warnings": warnings, "isProtein": True,
    }
