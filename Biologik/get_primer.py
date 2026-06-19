#!/usr/bin/env python3
from pathlib import Path

COMPLEMENT = str.maketrans(
    "ACGTRYKMSWBDHVNacgtrykmswbdhvn",
    "TGCAYRMKSWVHDBNtgcayrmkswvhdbn",
)

VALID_IUPAC = frozenset("ACGTRYKMSWBDHVN")


def read_fasta_sequence(fasta_file: str) -> str:
    path = Path(fasta_file)
    if not path.exists():
        raise FileNotFoundError(f"FASTA file not found: {fasta_file}")

    lines = path.read_text().splitlines()
    headers = [line for line in lines if line.startswith(">")]
    if len(headers) > 1:
        raise ValueError(
            f"Expected a single-sequence FASTA file, found {len(headers)} sequences"
        )

    seq = "".join(line.strip() for line in lines if not line.startswith(">"))
    seq = "".join(seq.split()).upper()

    if not seq:
        raise ValueError("No sequence found in FASTA file")

    invalid = set(seq) - VALID_IUPAC
    if invalid:
        raise ValueError(
            f"Sequence contains invalid characters: {', '.join(sorted(invalid))}"
        )

    return seq


def rc(seq: str) -> str:
    return seq.translate(COMPLEMENT)[::-1]


def get_primer_sequences(fasta_file: str, primer_length: int = 25) -> tuple:
    seq = read_fasta_sequence(fasta_file)

    if len(seq) < primer_length:
        raise ValueError(f"Sequence must be at least {primer_length} bp long")

    sense = seq[:primer_length]
    antisense = rc(seq[-primer_length:])

    return sense, antisense
