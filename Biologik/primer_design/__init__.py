"""Primer design: selection, Tm balancing, evaluation, Golden Gate extensions.

Public entry point for server, tests and CLI:

    from Biologik.primer_design import design_primers

    result = design_primers(sequence="ATG...", ext_type="type0.3")
    result["primerFw"], result["tmFw"], result["q5AnnealingTemp"]

``design_primers`` returns a dict that can be serialized directly as JSON,
and raises ``ValueError`` if no primer pair is found.

This package imports primer3 (see ``Biologik/requirements.txt``).
``Biologik.level0_design``, in contrast, needs no external packages.
"""

from .add_extensions import TYPE_EXTENSIONS, add_extensions
from .calc_tm import (
    BalancingError,
    balance_primers,
    find_best_primers,
    q5_annealing_temp,
    tm_wallace,
)
from .evaluate_primer import evaluate_primer
from .get_primer import (
    get_primer_sequences,
    normalise_sequence,
    parse_fasta,
    rc,
    read_fasta_sequence,
    resolve_sequence,
    slice_primers,
)
from .primer_pipeline import build_result, design_primers, format_result

__all__ = [
    "TYPE_EXTENSIONS",
    "add_extensions",
    "BalancingError",
    "balance_primers",
    "build_result",
    "design_primers",
    "evaluate_primer",
    "find_best_primers",
    "format_result",
    "get_primer_sequences",
    "normalise_sequence",
    "parse_fasta",
    "q5_annealing_temp",
    "rc",
    "read_fasta_sequence",
    "resolve_sequence",
    "slice_primers",
    "tm_wallace",
]
