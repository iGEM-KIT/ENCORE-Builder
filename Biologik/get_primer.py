#!/usr/bin/env python3
from pathlib import Path

COMPLEMENT = str.maketrans("ACGTRYKMSWBDHVNacgtrykmswbdhvn",
    "TGCAYRMKSWVHDBNtgcayrmkswvhdbn")
    #definiert die Komplementierung der DNA-Basen, damit die reverse complement gebildet werden kann

def read_fasta_sequence(fasta_file: str) -> str:
    #liest die Sequenz aus einer FASTA-Datei ein und gibt sie als String zurück
    path = Path(fasta_file)
    if not path.exists():
        raise FileNotFoundError(f"FASTA file not found: {fasta_file}")

    lines = path.read_text().splitlines()
    seq = "".join(line.strip() for line in lines if not line.startswith(">"))
    seq = "".join(seq.split()).upper()

    if not seq:
        raise ValueError("No sequence found in FASTA file")

    return seq

def rc(seq: str) -> str:
    #wandelt die Sequenz in die reverse complement um
    return seq.translate(COMPLEMENT)[::-1]

def get_primer_sequences(fasta_file: str, primer_length: int = 25):
    #Extrahiert die Primer Sequenzen aus der FASTA-Datei basierend auf der angegebenen Primerlänge (25bp)

    seq = read_fasta_sequence(fasta_file)

    if len(seq) < primer_length:
        raise ValueError(f"Sequence must be at least {primer_length} bp long")

    sense = seq[:primer_length]
    antisense = rc(seq[-primer_length:])

    return sense, antisense
