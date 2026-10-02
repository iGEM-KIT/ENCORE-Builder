import json
import subprocess
import sys

import pytest

from Biologik.level0_design.design import attach_adapter, build_genbank, design_construct, make_primer_pair
from Biologik.level0_design.genbank_writer import location_span
from Biologik.level0_design.parts_db import load_parts
from Biologik.level0_design.sequence import reverse_complement, validate_cargo


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

    assert len(design['level0']['cargoModule']) + len(design['level0']['ncModule']) == 10
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
    assert len(response['design']['level0']['cargoModule']) == 5


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
        'nanocompartments', 'promoters', 'surfaceMarkers',
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


ADAPTER_IDS = ['0.1', '0.1rc', '0.2', '0.3', '0.4', '0.5', '0.5rc']


def test_all_seven_type_overhang_adapters_are_in_the_database():
    adapters = {a['id']: a for a in load_parts()['type_overhangs']}
    assert sorted(adapters) == sorted(ADAPTER_IDS)
    assert adapters['0.1']['used_for_modules'] == ['nc_site']
    assert adapters['0.5rc']['used_for_modules'] == ['cargo_site']
    assert adapters['0.3']['used_for_modules'] == ['nc_site', 'cargo_site']


@pytest.mark.parametrize('adapter_id', ADAPTER_IDS)
@pytest.mark.parametrize('cds', ['ATGAAATTTGAAATGAAATTTGAAATGAAATTTGAA', 'GGG'])
def test_attach_adapter_replaces_the_filler_and_keeps_every_overhang_in_place(adapter_id, cds):
    adapter = next(a for a in load_parts()['type_overhangs'] if a['id'] == adapter_id)
    result = attach_adapter(adapter_id, cds)
    ins_start = int(result['insert']['location'].split('..')[0])

    # filler AAAA gone, CDS in its place, flanks untouched
    assert result['length'] == len(adapter['sequence']) - 4 + len(cds)
    assert result['sequence'][ins_start - 1:ins_start - 1 + len(cds)] == cds
    assert result['sequence'][:ins_start - 1] == adapter['sequence'][:ins_start - 1]
    assert result['sequence'].endswith(adapter['sequence'][ins_start + 3:])
    assert result['sequence'].startswith('GAAGAC') and result['sequence'].endswith('GTCTTC')

    # every overhang keeps its identity (attach_adapter itself already re-checks the positions)
    before = {o['role']: o['sequence_top_strand'] for o in adapter['overhangs']}
    after = {o['role']: o['sequence_top_strand'] for o in result['overhangs']}
    assert before == after
    assert [o['role'] for o in result['overhangs']] == [o['role'] for o in adapter['overhangs']]
    assert len(result['bbsiSites']) == 2


def test_attach_adapter_gives_the_expected_level2_overhangs_for_each_site():
    roles = lambda adapter_id: {o['role']: o['sequence_top_strand'] for o in attach_adapter(adapter_id, 'ATGAAATTT')['overhangs']}
    assert roles('0.1')['level2_N'] == 'TGAT'
    assert roles('0.5')['level2_C'] == 'AATG'
    assert roles('0.1rc')['level2_N'] == 'CCAA'
    assert roles('0.5rc')['level2_C'] == 'CGTT'
    assert 'level2_N' not in roles('0.3') and 'level2_C' not in roles('0.3')


@pytest.mark.parametrize('bad', ['', 'ATGN', 'atg x'])
def test_attach_adapter_rejects_an_invalid_insert(bad):
    with pytest.raises(ValueError):
        attach_adapter('0.3', bad)


def test_attach_adapter_rejects_an_unknown_adapter():
    with pytest.raises(ValueError):
        attach_adapter('0.9', 'ATGAAATTT')


def test_design_builds_a_level0_construct_for_every_user_entered_sequence():
    # Cargo (immer) + eigene Cargo-Modul-Sequenz (Type 0.1 -> rc-Adapter) + eigene NC-Sequenz (Type 0.5 -> 0.5)
    design = _design(
        cargo_slots={'1': {'kind': 'custom', 'label': 'Part A', 'seq': 'ATG' + 'AAA' * 12},
                     '2': {'kind': 'linker', 'id': 'GSSS2'}, '4': {'kind': 'ncs'}, '5': {'kind': 'ncs'}},
        nc_slots={'1': {'kind': 'ncs'}, '2': {'kind': 'ncs'}, '4': {'kind': 'linker', 'id': 'GSSS2'},
                  '5': {'kind': 'custom', 'label': 'Part B', 'seq': 'ATG' + 'CCC' * 10}},
    )
    assert len(design['level0Constructs']) == 10      # every module gets one, user-entered or toolkit
    constructs = {c['label']: c for c in design['level0Constructs'] if c['isUser']}
    assert list(constructs) == ['Part A', 'GFP', 'Part B']
    assert [constructs[k]['adapter'] for k in constructs] == ['0.1rc', '0.3', '0.5']
    assert constructs['Part A']['module'] == 'cargo_site' and constructs['Part B']['module'] == 'nc_site'

    # Cargo-Modul-Teile werden als Reverse Complement eingesetzt, NC-Teile unveraendert
    assert constructs['GFP']['insert']['sequence'] == design['cargo']['sequence']      # shown in its own reading direction
    assert constructs['Part B']['insert']['sequence'] == 'ATG' + 'CCC' * 10
    for c in constructs.values():
        assert c['sequence'].startswith('GAAGAC') and c['sequence'].endswith('GTCTTC')
        assert c['insert']['sequence'] in c['sequence']
        i0, i1 = map(int, c['insert']['location'].split('..'))
        assert c['sequence'][i0 - 1:i1] == c['insert']['sequence']

    genbank = build_genbank(design)
    assert 'LOCUS       Level0_Part-A_Type0.1_0.1rc' in genbank
    assert 'with-overhangs' not in genbank
    assert genbank.count('//') == genbank.count('LOCUS')


def test_every_module_gets_a_level0_construct_and_only_user_input_is_flagged():
    design = _design()
    constructs = design['level0Constructs']
    assert [(c['module'], c['slot']) for c in constructs] == \
        [('cargo_site', n) for n in range(1, 6)] + [('nc_site', n) for n in range(1, 6)]
    assert [c['adapter'] for c in constructs] == ['0.1rc', '0.2', '0.3', '0.4', '0.5rc', '0.1', '0.2', '0.3', '0.4', '0.5']
    assert [c['label'] for c in constructs if c['isUser']] == ['GFP']
    # toolkit parts without a real sequence in the parts database are flagged as placeholders
    assert all(not c['isReal'] for c in constructs if not c['isUser'])


def _backbone_orientation(c):
    pl = c['plasmid']
    return pl['sequence'], pl['insertStart'], pl['insertEnd']


def test_level0_plasmid_is_cloned_with_bbsi_at_the_right_junctions():
    import re
    from Biologik.level0_design.parts_db import find_part
    backbone = find_part('level0_backbones', 'pAGM9121-lvl0-dest')
    for c in _design()['level0Constructs']:
        plasmid = c['plasmid']
        seq, ins_start, ins_end = _backbone_orientation(c)
        fragment_len = ins_end - ins_start + 1
        # stuffer (602 bp between NLvl0 and CLvl0, overhangs included) replaced by the adapter fragment
        assert plasmid['length'] == backbone['length_bp'] - 602 + fragment_len
        assert seq[:2049] == backbone['sequence'][:2049]
        assert seq[ins_end:] == backbone['sequence'][2651:]
        # the adapter's BbsI sites and the backbone's stuffer BbsI sites are gone; BsaI sites regenerated at both seams
        assert 'GAAGAC' not in seq and 'GTCTTC' not in seq
        assert seq[2046:2052] == 'GGTCTC' and seq[ins_end - 3:ins_end + 3] == 'GAGACC'
        # the part's own insert is inside the cloned fragment
        in_backbone_orientation = reverse_complement(c['insert']['sequence']) if c['rotated'] else c['insert']['sequence']
        assert in_backbone_orientation in seq[ins_start - 1:ins_end]
        # GenBank carries the backbone's surviving annotations plus the adapter's overhangs and the insert,
        # but nothing from the removed stuffer
        gb = plasmid['genbank']
        assert gb.count('//') == gb.count('LOCUS') == 1 and 'circular' in gb
        for kept in ('/label="SmR"', '/label="ori"', '/label="BsaI rec site"', '/label="0N"', f'/label="{c["label"]}"'):
            assert kept in gb
        for gone in ('lacZ-alpha', 'pL0-P', 'MCS', 'BbsI rec site', 'lac promoter', 'M13 rev'):
            assert f'/label="{gone}' not in gb
        positions = [int(n) for loc in re.findall(r'^     \S+\s+(\S+)$', gb, re.M) for n in re.findall(r'\d+', loc)]
        assert max(positions) <= plasmid['length']


def test_level0_plasmid_has_the_right_sticky_ends_per_adapter():
    # the 4 nt overhangs of the cloned fragment match the backbone's NLvl0/CLvl0 top strand (CTCA ... CGAG)
    for c in _design()['level0Constructs']:
        seq, _, ins_end = _backbone_orientation(c)
        assert seq[2049:2053] == 'CTCA'
        assert seq[ins_end - 4:ins_end] == 'CGAG'


def test_cargo_site_constructs_are_rotated_so_the_cargo_reads_5_to_3_left_to_right():
    import re
    design = _design()
    constructs = design['level0Constructs']
    assert [c['rotated'] for c in constructs] == [True] * 5 + [False] * 5
    assert [c['plasmidStrand'] for c in constructs] == ['antisense'] * 5 + ['sense'] * 5
    cargo = next(c for c in constructs if c['isUser'])
    # the cargo CDS appears exactly as typed (ATG first); the plasmid top strand carries its reverse complement
    assert cargo['insert']['sequence'] == design['cargo']['sequence'] and cargo['insert']['sequence'] in cargo['sequence']
    assert design['cargo']['sequenceAntisense'] in cargo['plasmid']['sequence']      # the plasmid keeps the backbone's orientation
    # rotated adapter: still BbsI-flanked, and the outer overhangs are the old ones, mirrored (CTCA..CGAG -> CTCG..TGAG)
    assert cargo['sequence'].startswith('GAAGAC') and cargo['sequence'].endswith('GTCTTC')
    tops = {o['role']: o['sequence_top_strand'] for o in cargo['overhangs']}
    assert tops['level0_C'] == 'CTCG' and tops['level0_N'] == 'TGAG'
    for o in cargo['overhangs'] + cargo['bbsiSites']:
        a, b = location_span(o['location'])
        assert cargo['sequence'][a - 1:b] == o['sequence_top_strand']
    # annotation: CDS on the plain strand in the rotated construct, on the complement strand in the plasmid
    cds = lambda gb, label='GFP': re.search(r'^     CDS\s+(\S+)\n(?:\s+/(?!label)[^\n]*\n)*\s+/label="' + label + '"', gb, re.M).group(1)
    assert not cds(cargo['genbank']).startswith('complement(')
    assert cds(cargo['plasmid']['genbank']).startswith('complement(')      # antisense on the plasmid's top strand
    # NC site is unchanged: sense on both
    nc = next(c for c in constructs if c['module'] == 'nc_site' and c['slot'] == 3)
    assert [c['strand'] for c in constructs] == ['antisense'] * 5 + ['sense'] * 5      # every cargo-site part is labelled antisense
    assert nc['strand'] == 'sense' and not cds(nc['plasmid']['genbank'], 'E-Tm').startswith('complement(')


def test_libraries_ship_the_level0_backbone_with_a_ready_genbank_text():
    from Biologik.level0_design.data import get_libraries
    backbone = get_libraries()['level0Backbones'][0]
    gb = backbone['genbank']
    assert gb.startswith('LOCUS       pAGM9121') and '2659 bp' in gb and 'circular' in gb
    assert gb.count('//') == 1 and gb.strip().endswith('//')
    for label in ('SmR', 'ori', 'lacZ-alpha', 'BbsI rec site', 'BsaI rec site'):
        assert f'/label="{label}"' in gb
    assert backbone['sequence'] and '/translation' not in gb


def test_design_response_only_carries_what_the_ui_and_export_use():
    design = _design()
    assert sorted(design) == ['cargo', 'cargoSlots', 'level0', 'level0Constructs', 'level2', 'nanocompartment',
                              'ncSlots', 'primers', 'targetingPeptide']
    assert sorted(design['cargo']) == ['bp', 'label', 'sequence', 'sequenceAntisense']
    assert sorted(design['level2']['promoter']) == ['bp', 'id', 'label']
