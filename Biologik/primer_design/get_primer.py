#!/usr/bin/env python3
from __future__ import annotations

"""Sequenz-Beschaffung für das Primerdesign.

Die Sequenz kann aus zwei Quellen kommen:

* einem FASTA-File (so ruft die CLI es auf), oder
* direkt als String (so ruft der Webserver es auf — dort liegt die Sequenz
  bereits im Request und soll nicht erst auf die Platte geschrieben werden).

Deshalb ist das Einlesen in drei Teile zerlegt: ``parse_fasta`` (reiner Text,
keine Datei-IO), ``read_fasta_sequence`` (Datei -> Sequenz, unverändertes
Verhalten) und ``resolve_sequence`` (nimmt entgegen, was da ist).
"""

from pathlib import Path

COMPLEMENT = str.maketrans(
    "ACGTRYKMSWBDHVNacgtrykmswbdhvn",
    "TGCAYRMKSWVHDBNtgcayrmkswvhdbn",
)

VALID_IUPAC = frozenset("ACGTRYKMSWBDHVN")


def normalise_sequence(sequence: str) -> str:
    """Grossbuchstaben, Whitespace raus, IUPAC-Zeichen prüfen."""
    seq = "".join((sequence or "").split()).upper()

    if not seq:
        raise ValueError("No sequence found in FASTA file")

    invalid = set(seq) - VALID_IUPAC
    if invalid:
        raise ValueError(
            f"Sequence contains invalid characters: {', '.join(sorted(invalid))}"
        )

    return seq


def parse_fasta(text: str) -> str:
    """FASTA-Text mit genau einem Record -> Sequenz. Ohne Datei-Zugriff."""
    lines = text.splitlines()
    headers = [line for line in lines if line.startswith(">")]
    if len(headers) > 1:
        raise ValueError(
            f"Expected a single-sequence FASTA file, found {len(headers)} sequences"
        )

    seq = "".join(line.strip() for line in lines if not line.startswith(">"))
    return normalise_sequence(seq)


def read_fasta_sequence(fasta_file: str) -> str:
    """FASTA-Datei -> Sequenz. Verhalten unverändert."""
    path = Path(fasta_file)
    if not path.exists():
        raise FileNotFoundError(f"FASTA file not found: {fasta_file}")

    return parse_fasta(path.read_text())


def resolve_sequence(sequence: str | None = None, fasta_file: str | None = None) -> str:
    """Genau eine der beiden Quellen muss gesetzt sein."""
    if sequence is not None and fasta_file is not None:
        raise ValueError("Provide either `sequence` or `fasta_file`, not both.")
    if sequence is not None:
        return normalise_sequence(sequence)
    if fasta_file is not None:
        return read_fasta_sequence(fasta_file)
    raise ValueError("Provide either `sequence` or `fasta_file`.")


def rc(seq: str) -> str:
    return seq.translate(COMPLEMENT)[::-1]


def slice_primers(seq: str, primer_length: int = 25) -> tuple:
    """Aus einer bereits eingelesenen Sequenz die beiden Rohprimer schneiden."""
    if len(seq) < primer_length:
        raise ValueError(f"Sequence must be at least {primer_length} bp long")

    sense = seq[:primer_length]
    antisense = rc(seq[-primer_length:])

    return sense, antisense


def get_primer_sequences(
    fasta_file: str | None = None,
    primer_length: int = 25,
    *,
    sequence: str | None = None,
) -> tuple:
    """Rohprimer aus FASTA-Datei ODER aus einer Sequenz."""
    seq = resolve_sequence(sequence=sequence, fasta_file=fasta_file)
    return slice_primers(seq, primer_length=primer_length)
