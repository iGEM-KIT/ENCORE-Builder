#!/usr/bin/env python3
"""Obtaining the sequence for primer design.

The sequence can come from two sources:

* a FASTA file (this is how the CLI calls it), or
* directly as a string (this is how the web server calls it: there the sequence
  is already in the request and should not first be written to disk).

That is why reading is split into three parts: ``parse_fasta`` (plain text,
no file IO), ``read_fasta_sequence`` (file -> sequence, unchanged
behaviour) and ``resolve_sequence`` (takes whatever is there).
"""

from __future__ import annotations


from pathlib import Path

COMPLEMENT = str.maketrans(
    "ACGTRYKMSWBDHVNacgtrykmswbdhvn",
    "TGCAYRMKSWVHDBNtgcayrmkswvhdbn",
)

VALID_IUPAC = frozenset("ACGTRYKMSWBDHVN")


def normalise_sequence(sequence: str) -> str:
    """Upper case, whitespace removed, IUPAC characters checked."""
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
    """FASTA text with exactly one record -> sequence. Without file access."""
    lines = text.splitlines()
    headers = [line for line in lines if line.startswith(">")]
    if len(headers) > 1:
        raise ValueError(
            f"Expected a single-sequence FASTA file, found {len(headers)} sequences"
        )

    seq = "".join(line.strip() for line in lines if not line.startswith(">"))
    return normalise_sequence(seq)


def read_fasta_sequence(fasta_file: str) -> str:
    """FASTA file -> sequence. Behaviour unchanged."""
    path = Path(fasta_file)
    if not path.exists():
        raise FileNotFoundError(f"FASTA file not found: {fasta_file}")

    return parse_fasta(path.read_text())


def resolve_sequence(sequence: str | None = None, fasta_file: str | None = None) -> str:
    """Exactly one of the two sources must be set."""
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
    """Cut the two raw primers from an already read sequence."""
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
    """Raw primers from a FASTA file OR from a sequence."""
    seq = resolve_sequence(sequence=sequence, fasta_file=fasta_file)
    return slice_primers(seq, primer_length=primer_length)
