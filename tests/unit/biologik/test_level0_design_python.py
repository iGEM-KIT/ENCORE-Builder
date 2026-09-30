import json
import subprocess
import sys

from Biologik.level0_design.design import build_genbank, design_construct, make_primer_pair
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


CARGO = 'ATGAAATTTGAAATGAAATTTGAAATGAAATTTGAA'

# Die zwei Fusionsrichtungen sind seit dem Slot-Umbau kein eigener 'fusion'-Parameter
# mehr, sondern ergeben sich daraus, in welchem Cargo-Modul-Slot (Type 0.1 oder 0.5)
# das Targeting-Peptid sitzt. Ein Linker im Nachbarslot ist Pflicht (siehe
# resolve_slots in design.py) — ohne ihn lehnt design_construct die Eingabe ab.
CARGO_SLOTS_C_TERM = {'1': {'kind': 'tp'}, '2': {'kind': 'linker', 'id': 'GSSS2'}}
CARGO_SLOTS_N_TERM = {'5': {'kind': 'tp'}, '4': {'kind': 'linker', 'id': 'GSSS2'}}


def _design(cargo_slots=None, nc_slots=None, **overrides):
    return design_construct(dict(
        {
            'nanocompartment': 'tmari',
            'cargoSeq': CARGO,
            'cargoLabel': 'GFP',
            'cargoSlots': cargo_slots if cargo_slots is not None else CARGO_SLOTS_C_TERM,
            'ncSlots': nc_slots or {},
        },
        **overrides,
    ))


def test_design_construct_builds_level0_modules():
    design = _design()

    assert design['level0']['total'] == 10
    assert len(design['level0']['cargoModule']) == 5
    assert len(design['level0']['ncModule']) == 5
    assert design['level0']['cargoModule'][0]['role'] == 'targeting-peptide'


def test_make_primer_pair_and_genbank_export():
    primers = make_primer_pair('ATGAAATTTGAA', 'CCAA', 'GCAA')
    assert len(primers) == 2

    # build_genbank erwartet die volle design_construct()-Antwort (cargoSlots, ncSlots,
    # sequenceAntisense, ...) — ein von Hand gebautes Teil-Dict war hier frueher schon
    # einmal veraltet, ohne dass es auffiel. Deshalb jetzt gegen ein echtes Ergebnis.
    design = _design()
    genbank = build_genbank(design)
    assert 'LOCUS       Level1_Cargo-Module_GFP' in genbank
    assert 'LOCUS       Cargo_GFP ' in genbank
    assert '/label="GFP"' in genbank
    assert genbank.count('//') == genbank.count('LOCUS')


def test_json_cli_connects_backend_request_to_biologik():
    request = {
        'nanocompartment': 'tmari',
        'cargoSeq': CARGO,
        'cargoLabel': 'CliCargo',
        'cargoSlots': CARGO_SLOTS_C_TERM,
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
        'cargoPresets', 'level0Backbones', 'level1Backbones', 'level2Backbones', 'linkers',
        'nanocompartments', 'promoters', 'surfaceMarkers', 'terminators', 'typeOverhangs',
    ]
    assert [m['id'] for m in libraries['surfaceMarkers']] == ['spycatcher', 'spytag']
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
    result = _run_cli('design', {'nanocompartment': 'gibtsnicht', 'cargoSeq': CARGO})
    response = json.loads(result.stdout)

    assert result.returncode == 1
    assert response['ok'] is False
    assert 'gibtsnicht' in response['error']
    assert result.stderr.strip() == ''


def test_stop_codon_follows_the_targeting_peptide_slot():
    # Der ORF endet am C-Terminus des Fusionsproteins. Sitzt das TP in Type 0.1, ist
    # das der C-Terminus (Cargo liegt "vor" ihm im ORF); sitzt es in Type 0.5, traegt
    # stattdessen der NCS in Type 0.2 (direkt hinter der Cargo) das Stopcodon.
    c_term_module = _design(cargo_slots=CARGO_SLOTS_C_TERM)['level0']['cargoModule']
    n_term_module = _design(cargo_slots=CARGO_SLOTS_N_TERM)['level0']['cargoModule']

    assert [p['stop'] for p in c_term_module] == [True, False, False, False, False]
    assert [p['stop'] for p in n_term_module] == [False, True, False, False, False]
    assert c_term_module[0]['role'] == 'targeting-peptide'
    assert n_term_module[1]['role'] == 'ncs'


def test_surface_marker_sits_at_the_chosen_terminus():
    # Ein Marker (oder jede andere CDS) in Type 0.1/0.5 braucht zwingend einen Linker
    # im Nachbarslot (0.2/0.4) — anders als frueher gibt es keinen automatischen L1-Linker
    # mehr, die Wahl liegt beim Nutzer.
    n_term = _design(nc_slots={'1': {'kind': 'marker', 'id': 'spycatcher'}, '2': {'kind': 'linker', 'id': 'GSSS2'}})['level0']['ncModule']
    c_term = _design(nc_slots={'4': {'kind': 'linker', 'id': 'GSSS2'}, '5': {'kind': 'marker', 'id': 'spycatcher'}})['level0']['ncModule']

    assert n_term[0]['kind'] == 'mark' and n_term[1]['role'] == 'nc-linker'
    assert c_term[4]['kind'] == 'mark' and c_term[3]['role'] == 'nc-linker'

    # Das Stopcodon wandert an das neue 3'-Ende des ORFs mit.
    assert n_term[3]['stop'] is True
    assert c_term[4]['stop'] is True


def test_without_a_marker_the_slots_stay_inert_spacers():
    nc_module = _design()['level0']['ncModule']

    assert [p['role'] for p in nc_module] == ['ncs', 'ncs', 'shell', 'ncs', 'ncs']
    assert [p['stop'] for p in nc_module] == [False, False, False, True, False]


def test_unknown_surface_marker_is_rejected():
    try:
        _design(nc_slots={'1': {'kind': 'marker', 'id': 'gibtsnicht'}, '2': {'kind': 'linker', 'id': 'GSSS2'}})
    except ValueError as error:
        assert 'gibtsnicht' in str(error)
    else:
        raise AssertionError('unknown marker should raise')
