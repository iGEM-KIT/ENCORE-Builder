#!/usr/bin/env python3
import argparse
import warnings
from add_extensions import add_extensions
from calc_tm import find_best_primers
from evaluate_primer import evaluate_primer

warnings.filterwarnings('ignore', category=UserWarning)


def print_final_result(
    best_result: dict,
    ext_type: str | None = None,
    ext_fw: str | None = None,
    ext_rv: str | None = None,
) -> None:
    primer_fw = best_result['primer_fw']
    primer_rv = best_result['primer_rv']
    tm_fw = best_result['tm_fw']
    tm_rv = best_result['tm_rv']
    q5_temp = best_result['q5_annealing_temp']
    evaluation = best_result['evaluation']

    if ext_type or ext_fw or ext_rv:
        extended_fw, extended_rv = add_extensions(
            primer_fw,
            primer_rv,
            ext_type=ext_type,
            ext_fw=ext_fw,
            ext_rv=ext_rv,
        )
        evaluation = evaluate_primer(extended_fw, extended_rv)
        primer_fw = extended_fw
        primer_rv = extended_rv
        # q5_temp unchanged: 5' extensions don't participate in the initial annealing step

    print(f"Forward primer:  {primer_fw} (len={len(primer_fw)}, Tm={tm_fw:.1f})")
    print(f"Reverse primer:  {primer_rv} (len={len(primer_rv)}, Tm={tm_rv:.1f})")
    print(f"Q5 annealing temperature: {q5_temp:.1f}°C (based on Tm={min(tm_fw, tm_rv):.1f}°C)")

    if evaluation['valid']:
        print('Status: VALID')
    else:
        print(f"Status: BEST AVAILABLE ({len(evaluation['issues'])} issue(s))")
        if evaluation['issues']:
            print('Issues:')
            for issue in evaluation['issues']:
                print(f"  - {issue}")


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
    args = parser.parse_args()

    if args.ext_type and (args.ext_fw or args.ext_rv):
        parser.error('Use either --type or --ext-fw/--ext-rv, not both.')

    best_result = find_best_primers(args.fasta_file, min_len=args.min_len, max_len=args.max_len)

    if not best_result:
        print('No valid primer pair found.')
        raise SystemExit(1)

    print_final_result(best_result, ext_type=args.ext_type, ext_fw=args.ext_fw, ext_rv=args.ext_rv)


if __name__ == '__main__':
    main()
