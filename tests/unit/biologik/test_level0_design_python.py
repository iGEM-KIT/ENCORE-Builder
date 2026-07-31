import pytest

from Biologik.level0_design.design import build_fasta, design_construct, make_primer_pair
from Biologik.level0_design.sequence import validate_cargo


def test_validate_cargo_rejects_stop_codon_and_short_sequences():
    cargo = validate_cargo('ATGAAATAG', min_bp=30)
    assert cargo['ok'] is False
    assert 'Stop codon at the end' in cargo['errors'][0]


def test_design_construct_builds_level0_modules():
    design = design_construct(
        {
            'nanocompartment': 'tmari',
            'cargoSeq': 'ATGAAATTTGAAATGAAATTTGAAATGAAATTTGAA',
            'cargoLabel': 'TestCargo',
            'fusion': 'C',
        }
    )

    assert design['level0']['total'] == 10
    assert len(design['level0']['cargoModule']) == 5
    assert len(design['level0']['ncModule']) == 5
    assert design['level0']['cargoModule'][0]['role'] == 'targeting-peptide'


def test_make_primer_pair_and_fasta_export():
    primers = make_primer_pair('ATGAAATTTGAA', 'CCAA', 'GCAA')
    assert len(primers) == 2
    fasta = build_fasta(
        {
            'nanocompartment': {'id': 'tmari', 'shell': 'E-Tm', 'shellBp': 516},
            'linker': {'id': 'GSSS2', 'bp': 24},
            'cargo': {'label': 'TestCargo', 'sequence': 'ATGAAATTTGAAATGAAATTTGAAATGAAATTTGAA'},
            'targetingPeptide': 'TP-Tm',
            'level2': {'promoter': {'id': 'GAL110', 'label': 'GAL1-10'}},
            'fusion': 'C',
        }
    )
    assert 'Level1_Cargo-Module_C-terminal' in fasta
