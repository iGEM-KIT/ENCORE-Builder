"""Tests of Biologik/primer_design: sequence reading, slicing, Tm balancing, evaluation and the pipeline.

The thermodynamics need primer3-py (Biologik/requirements.txt); those tests are skipped where it is not installed.
The helpers that need no primer3 (reading, slicing, extensions, the Wallace Tm) always run.
"""

import pytest

from Biologik.primer_design.add_extensions import TYPE_EXTENSIONS, add_extensions
from Biologik.primer_design.get_primer import (
    normalise_sequence,
    parse_fasta,
    rc,
    resolve_sequence,
    slice_primers,
)

# A plain 300 bp coding-like sequence without long repeats, good enough for primer design
SEQ = (
    "ATGGCTAAAGGTGAAGAACTGTTCACCGGTGTTGTTCCAATCTTGGTTGAATTGGATGGTGATGTTAACGGTCACAAATTCTCTGTTTCTGGTGAAGGTGAAGGT"
    "GATGCTACTTACGGTAAATTGACCTTGAAATTCATTTGTACTACTGGTAAATTGCCAGTTCCATGGCCAACCTTGGTTACTACTTTCGGTTACGGTTTGCAATGT"
    "TTCGCTAGATACCCAGATCACATGAAACAACACGACTTCTTCAAGTCTGCCATGCCAGAAGGTTACGTTCAAGAAAGAACTATCTTCTTCAAGGATGACGGTAAC"
)


# Reading and slicing (no primer3 needed)

def test_normalise_sequence_uppercases_and_removes_whitespace():
    assert normalise_sequence(" atg c\nGt ") == "ATGCGT"


def test_normalise_sequence_rejects_empty_and_invalid_input():
    with pytest.raises(ValueError, match="No sequence"):
        normalise_sequence("  \n ")
    with pytest.raises(ValueError, match="invalid characters"):
        normalise_sequence("ATGC123")


def test_parse_fasta_reads_one_record_and_rejects_several():
    assert parse_fasta(">one\nATGC\nGGTT\n") == "ATGCGGTT"
    with pytest.raises(ValueError, match="single-sequence"):
        parse_fasta(">a\nATGC\n>b\nGGTT\n")


def test_resolve_sequence_needs_exactly_one_source():
    assert resolve_sequence(sequence="atgc") == "ATGC"
    with pytest.raises(ValueError, match="either"):
        resolve_sequence(sequence="ATGC", fasta_file="x.fasta")
    with pytest.raises(ValueError, match="either"):
        resolve_sequence()


def test_slice_primers_cuts_the_start_and_the_reverse_complement_of_the_end():
    sense, antisense = slice_primers(SEQ, primer_length=20)
    assert sense == SEQ[:20] and antisense == rc(SEQ[-20:]) and len(antisense) == 20
    assert rc(rc(SEQ)) == SEQ
    with pytest.raises(ValueError, match="at least"):
        slice_primers("ATGC", primer_length=20)


# Extensions

def test_type_extensions_are_prepended_to_the_annealing_part():
    fw, rv = add_extensions("ATGAAATTTGGG", "CCCAAATTTCAT", ext_type="type0.3")
    ext_fw, ext_rv = TYPE_EXTENSIONS["type0.3"]
    assert fw == ext_fw + "ATGAAATTTGGG" and rv == ext_rv + "CCCAAATTTCAT"
    assert add_extensions("atg", "cat") == ("ATG", "CAT")                      # no extension: only upper-cased
    assert add_extensions("ATG", "CAT", ext_fw="gg", ext_rv="aa") == ("GGATG", "AACAT")
    with pytest.raises(ValueError, match="Unknown type"):
        add_extensions("ATG", "CAT", ext_type="type9.9")


# Thermodynamics (primer3)

primer3 = pytest.importorskip("primer3")

from Biologik.primer_design.calc_tm import (  # noqa: E402  (needs primer3)
    BalancingError,
    balance_primers,
    find_best_primers,
    q5_annealing_temp,
    tm_wallace,
)
from Biologik.primer_design.evaluate_primer import evaluate_primer  # noqa: E402
from Biologik.primer_design.primer_pipeline import build_result, design_primers  # noqa: E402


def test_wallace_tm_counts_two_per_at_and_four_per_gc():
    assert tm_wallace("ATGC") == 2 * 2 + 4 * 2
    assert tm_wallace("AAAA") == 8 and tm_wallace("GGGG") == 16 and tm_wallace("atgc") == 12


@pytest.mark.parametrize("tm, expected", [(72, 70), (70, 68), (66, 63), (65, 62), (62, 58), (60, 56), (55, 50)])
def test_q5_annealing_temperature_is_below_the_lower_tm_by_a_step(tm, expected):
    assert q5_annealing_temp(tm, tm + 3) == expected                                # the lower Tm counts


def test_balance_primers_returns_a_pair_below_the_limit_with_close_melting_temperatures():
    sense, antisense = slice_primers(SEQ, primer_length=25)
    p1, p2, tm1, tm2 = balance_primers(sense, antisense)
    assert tm1 <= 72 and tm2 <= 72 and abs(tm1 - tm2) <= 2.0
    assert sense.startswith(p1) and antisense.startswith(p2)                        # only shortened at the 3' end
    assert len(p1) >= 18 and len(p2) >= 18


def test_balance_primers_gives_up_instead_of_going_below_the_minimum_length():
    with pytest.raises(BalancingError):
        balance_primers("GC" * 12, "GC" * 12, min_len=18, max_tm=40)


def test_evaluate_primer_has_the_documented_shape():
    fw, rv = slice_primers(SEQ, primer_length=22)
    result = evaluate_primer(fw, rv)
    assert {"valid", "issues", "recommendation", "hetero_dimer_dG", "self_fw_dG", "self_rv_dG", "hairpin_fw_dG", "hairpin_rv_dG"} <= set(result)
    assert result["valid"] is (result["issues"] == [])


def test_evaluate_primer_flags_a_self_complementary_primer():
    palindrome = "GCGCGCGCGCGCGCGCGCGC"
    result = evaluate_primer(palindrome, palindrome)
    assert result["valid"] is False and result["issues"]
    assert any("dimer" in issue.lower() or "hairpin" in issue.lower() for issue in result["issues"])


def test_find_best_primers_returns_a_balanced_pair_for_a_normal_sequence():
    best = find_best_primers(sequence=SEQ)
    assert best is not None
    assert 18 <= best["primer_len"] <= 25 and abs(best["tm_fw"] - best["tm_rv"]) <= 2.0
    assert best["primer_fw"] == SEQ[:len(best["primer_fw"])]


def test_design_primers_returns_a_json_ready_dict_and_keeps_tm_on_the_annealing_part():
    result = design_primers(sequence=SEQ, ext_type="type0.3")
    assert result["primerFw"] == TYPE_EXTENSIONS["type0.3"][0] + result["annealFw"]
    assert result["primerRv"] == TYPE_EXTENSIONS["type0.3"][1] + result["annealRv"]
    assert result["lengthFw"] == len(result["primerFw"]) and result["lengthRv"] == len(result["primerRv"])
    # annealLength is the length the pair was cut at; balancing may then shorten a primer by a few bases at the 3' end
    assert result["annealLength"] >= max(len(result["annealFw"]), len(result["annealRv"]))
    assert result["extension"]["type"] == "type0.3" and result["extension"]["fw"] == TYPE_EXTENSIONS["type0.3"][0]
    import json
    json.dumps(result)                                                              # serializable as it is


def test_design_primers_without_an_extension_has_none_and_rejects_conflicting_options():
    assert design_primers(sequence=SEQ)["extension"] is None
    with pytest.raises(ValueError, match="either"):
        design_primers(sequence=SEQ, ext_type="type0.3", ext_fw="GG")


def test_design_primers_raises_for_a_sequence_that_is_too_short():
    with pytest.raises(ValueError):
        design_primers(sequence="ATGC")


def test_build_result_reports_the_evaluation_of_the_extended_primers():
    best = find_best_primers(sequence=SEQ)
    plain = build_result(best)
    extended = build_result(best, ext_fw="GAAGACAA")
    assert plain["extension"] is None and extended["extension"]["fw"] == "GAAGACAA"
    assert extended["tmFw"] == plain["tmFw"]                                         # Tm stays on the annealing part
