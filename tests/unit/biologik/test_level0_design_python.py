import json
import subprocess
import sys

from Biologik.level0_design.design import build_fasta, design_construct, make_primer_pair
from Biologik.level0_design.sequence import validate_cargo


def test_validate_cargo_rejects_a_trailing_stop_codon():
    # Lang genug und im Raster — die einzige Regel, die hier greifen darf, ist
    # das Stopcodon am Ende. Deshalb ist errors[0] eindeutig.
    cargo = validate_cargo('ATGAAATTTGAAATGAAATTTGAAATGAAATTTTAG', min_bp=30)

    assert cargo['ok'] is False
    assert cargo['trailingStop'] == 'TAG'
    assert len(cargo['errors']) == 1
    assert 'Stop codon at the end' in cargo['errors'][0]


def test_validate_cargo_rejects_a_too_short_sequence():
    # Endet auf GAA, nicht auf einem Stopcodon — hier darf nur die
    # Laengenpruefung anschlagen.
    cargo = validate_cargo('ATGAAATTTGAA', min_bp=30)

    assert cargo['ok'] is False
    assert cargo['trailingStop'] is None
    assert len(cargo['errors']) == 1
    assert 'Sequence too short' in cargo['errors'][0]


def test_validate_cargo_accepts_a_fusion_ready_sequence():
    cargo = validate_cargo('ATGAAATTTGAAATGAAATTTGAAATGAAATTTGAA', min_bp=30)

    assert cargo['ok'] is True
    assert cargo['errors'] == []
    assert cargo['length'] == 36
    assert cargo['aa'] == 12


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


def test_json_cli_connects_backend_request_to_biologik():
    request = {
        'nanocompartment': 'tmari',
        'cargoSeq': 'ATGAAATTTGAAATGAAATTTGAAATGAAATTTGAA',
        'cargoLabel': 'CliCargo',
        'fusion': 'C',
    }
    result = subprocess.run(
        [sys.executable, '-m', 'Biologik.level0_design.cli'],
        input=json.dumps(request),
        text=True,
        capture_output=True,
        check=True,
    )

    response = json.loads(result.stdout)
    assert response['ok'] is True
    assert response['design']['cargo']['label'] == 'CliCargo'
    assert response['design']['level0']['total'] == 10

def _run_cli(command, payload):
    """Ruft cli.py so auf, wie server/utils/biologik.js es tut."""
    return subprocess.run(
        [sys.executable, '-m', 'Biologik.level0_design.cli', command],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
    )


def test_json_cli_serves_libraries():
    result = _run_cli('libraries', {})
    response = json.loads(result.stdout)

    assert result.returncode == 0
    assert response['ok'] is True
    libraries = response['libraries']
    assert sorted(libraries) == [
        'cargoPresets', 'linkers', 'nanocompartments', 'promoters', 'typeOverhangs'
    ]
    assert [nc['id'] for nc in libraries['nanocompartments']] == ['tmari', 'mxan', 'qther']


def test_json_cli_validates_cargo_without_failing():
    # Eine ungueltige Sequenz ist eine gueltige Antwort mit ok:false,
    # kein Fehler-Exit — sonst wuerde die API daraus faelschlich HTTP 500 machen.
    result = _run_cli('validate', {'cargoSeq': 'ATGAAATTTGAAATGAAATTTGAAATGAAATTTTAA'})
    response = json.loads(result.stdout)

    assert result.returncode == 0
    assert response['ok'] is True
    assert response['validation']['ok'] is False
    assert 'Stop codon at the end' in response['validation']['errors'][0]


def test_json_cli_reports_the_real_error_on_stdout():
    # cli.py beendet sich mit 1, legt die Meldung aber auf stdout ab. Die
    # Gegenstelle muss stdout auswerten, sonst geht der Grund verloren.
    result = _run_cli('design', {'nanocompartment': 'gibtsnicht', 'cargoSeq': 'ATG', 'fusion': 'C'})
    response = json.loads(result.stdout)

    assert result.returncode == 1
    assert response['ok'] is False
    assert 'gibtsnicht' in response['error']
    assert result.stderr.strip() == ''
