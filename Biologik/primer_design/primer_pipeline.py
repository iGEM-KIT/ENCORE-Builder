#!/usr/bin/env python3
from __future__ import annotations

"""Primer-Pipeline: Primer schneiden, Tm balancieren, bewerten, Extensions anhängen.

Zwei Nutzungsarten, dieselbe Logik:

* ``design_primers(...)`` gibt ein dict zurück — das ist der Einstiegspunkt für
  den Webserver und für Tests.
* die CLI (``main``) formatiert dasselbe dict als Text, wie bisher.

Aufruf als CLI (aus dem Repo-Wurzelverzeichnis, weil das Modul jetzt Teil des
Pakets ``Biologik.primer_design`` ist):

    python -m Biologik.primer_design.primer_pipeline sequenz.fasta
    python -m Biologik.primer_design.primer_pipeline sequenz.fasta --json
"""

import argparse
import json
import warnings

from .add_extensions import add_extensions
from .calc_tm import find_best_primers
from .evaluate_primer import evaluate_primer

warnings.filterwarnings('ignore', category=UserWarning)


def build_result(
    best_result: dict,
    ext_type: str | None = None,
    ext_fw: str | None = None,
    ext_rv: str | None = None,
) -> dict:
    """Rohergebnis + optionale Extensions -> serialisierbares dict.

    Wichtig (wie vorher): Tm und Q5-Temperatur beziehen sich auf den
    ANNEALING-Teil, nicht auf den verlängerten Primer — ein 5'-Überhang nimmt
    am ersten Annealing-Schritt nicht teil. Die Bewertung (Dimere/Hairpins)
    wird dagegen auf dem verlängerten Primer neu gerechnet, weil sich die
    Sekundärstruktur durch den Überhang sehr wohl ändert.
    """
    anneal_fw = best_result['primer_fw']
    anneal_rv = best_result['primer_rv']
    primer_fw = anneal_fw
    primer_rv = anneal_rv
    evaluation = best_result['evaluation']
    extension = None

    if ext_type or ext_fw or ext_rv:
        primer_fw, primer_rv = add_extensions(
            anneal_fw,
            anneal_rv,
            ext_type=ext_type,
            ext_fw=ext_fw,
            ext_rv=ext_rv,
        )
        evaluation = evaluate_primer(primer_fw, primer_rv)
        extension = {
            "type": ext_type,
            "fw": primer_fw[: len(primer_fw) - len(anneal_fw)] or None,
            "rv": primer_rv[: len(primer_rv) - len(anneal_rv)] or None,
        }

    return {
        "primerFw": primer_fw,
        "primerRv": primer_rv,
        "annealFw": anneal_fw,
        "annealRv": anneal_rv,
        "lengthFw": len(primer_fw),
        "lengthRv": len(primer_rv),
        "tmFw": best_result['tm_fw'],
        "tmRv": best_result['tm_rv'],
        "q5AnnealingTemp": best_result['q5_annealing_temp'],
        "annealLength": best_result['primer_len'],
        "extension": extension,
        "evaluation": evaluation,
        "valid": evaluation['valid'],
        "issues": evaluation['issues'],
    }


def design_primers(
    sequence: str | None = None,
    fasta_file: str | None = None,
    min_len: int = 18,
    max_len: int = 25,
    ext_type: str | None = None,
    ext_fw: str | None = None,
    ext_rv: str | None = None,
) -> dict:
    """Einstiegspunkt für Server und Tests: Sequenz rein, dict raus.

    Wirft ``ValueError``, wenn kein Primerpaar gefunden wird — genau wie
    ``level0_design.design.design_construct`` bei ungültigen Eingaben, damit
    die API-Schicht beides gleich auf HTTP 400 abbilden kann.
    """
    if ext_type and (ext_fw or ext_rv):
        raise ValueError('Use either `ext_type` or `ext_fw`/`ext_rv`, not both.')

    best_result = find_best_primers(
        fasta_file=fasta_file,
        min_len=min_len,
        max_len=max_len,
        sequence=sequence,
    )

    if not best_result:
        raise ValueError('No valid primer pair found.')

    return build_result(best_result, ext_type=ext_type, ext_fw=ext_fw, ext_rv=ext_rv)


def format_result(result: dict) -> str:
    """Dasselbe dict als Text — Wortlaut unverändert gegenüber der alten CLI."""
    lines = [
        f"Forward primer:  {result['primerFw']} (len={result['lengthFw']}, Tm={result['tmFw']:.1f})",
        f"Reverse primer:  {result['primerRv']} (len={result['lengthRv']}, Tm={result['tmRv']:.1f})",
        f"Q5 annealing temperature: {result['q5AnnealingTemp']:.1f}°C "
        f"(based on Tm={min(result['tmFw'], result['tmRv']):.1f}°C)",
    ]

    if result['valid']:
        lines.append('Status: VALID')
    else:
        lines.append(f"Status: BEST AVAILABLE ({len(result['issues'])} issue(s))")
        if result['issues']:
            lines.append('Issues:')
            for issue in result['issues']:
                lines.append(f"  - {issue}")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pipeline: extract primers, balance Tm, evaluate, and optionally add 5' extensions."
    )
    parser.add_argument('fasta_file', help='Input FASTA file')
    parser.add_argument('--min-len', type=int, default=18, help='Minimum primer length to test')
    parser.add_argument('--max-len', type=int, default=25, help='Maximum primer length to test')
    parser.add_argument('--type', dest='ext_type', help='Named extension type from add_extensions')
    parser.add_argument('--ext-fw', help="Explicit 5' extension sequence for forward primer")
    parser.add_argument('--ext-rv', help="Explicit 5' extension sequence for reverse primer")
    parser.add_argument('--json', action='store_true', help='Emit the result as JSON instead of text')
    args = parser.parse_args()

    if args.ext_type and (args.ext_fw or args.ext_rv):
        parser.error('Use either --type or --ext-fw/--ext-rv, not both.')

    try:
        result = design_primers(
            fasta_file=args.fasta_file,
            min_len=args.min_len,
            max_len=args.max_len,
            ext_type=args.ext_type,
            ext_fw=args.ext_fw,
            ext_rv=args.ext_rv,
        )
    except ValueError as err:
        print(str(err))
        raise SystemExit(1)

    print(json.dumps(result, indent=2) if args.json else format_result(result))


if __name__ == '__main__':
    main()
