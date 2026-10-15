import json
import random
import re
import subprocess
import sys

import pytest

from Biologik.level0_design.codon import cai, find_forbidden, optimize_cds, translate
from Biologik.level0_design.adapters import attach_adapter
from Biologik.level0_design.design import build_genbank, design_construct
from Biologik.level0_design.primers import make_primer_pair
from Biologik.level0_design.user_codons import codon_optimize_part
from Biologik.level0_design.genbank_writer import location_span
from Biologik.level0_design.parts_db import load_parts
from Biologik.level0_design.sequence import is_protein, reverse_complement, validate_cargo


def test_validate_cargo_takes_a_trailing_stop_codon_off_instead_of_rejecting_it():
    # The builder adds the stop codon itself, so an entered one is removed with a warning.
    cargo = validate_cargo('ATGAAATTTGAAATGAAATTTGAAATGAAATTTTAG', min_bp=30)

    assert cargo['ok'] is True and cargo['errors'] == []
    assert cargo['trailingStop'] == 'TAG' and cargo['clean'] == 'ATGAAATTTGAAATGAAATTTGAAATGAAATTT' and cargo['length'] == 33
    assert len(cargo['warnings']) == 1 and 'removes the stop codon at the end' in cargo['warnings'][0]
    protein = validate_cargo('MKFEMKFEMKFEMKF*', min_bp=30)
    assert protein['ok'] is True and protein['clean'] == 'MKFEMKFEMKFEMKF' and protein['trailingStop'] == '*'


def test_validate_cargo_rejects_a_too_short_sequence():
    # Ends in GAA, not in a stop codon; only the length check may fire here.
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

# The two fusion directions have not been a separate 'fusion' parameter since the slot rework,
# but follow from which cargo module slot (Type 0.1 or 0.5) holds the targeting peptide.
# A linker in the neighbouring slot is mandatory (see resolve_slots in slots.py); without it
# design_construct rejects the input.
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

    # build_genbank expects the full design_construct() answer (cargoSlots, ncSlots,
    # sequenceAntisense, ...); a hand-built partial dict was already outdated here once
    # without anyone noticing. So it now runs against a real result.
    design = _design()
    genbank = build_genbank(design)
    assert 'LOCUS       Level1_Cargo ' in genbank
    assert 'LOCUS       Level1_NC ' in genbank
    assert 'LOCUS       pESC-HIS_Level2_ENCORE-tmari ' in genbank
    assert 'LOCUS       Level0.3_GFP_Cargo ' in genbank
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
    """Calls cli.py the way server/utils/biologik.js does."""
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
        'cargoPresets', 'inteins', 'level0Backbones', 'level1Backbones', 'level2Backbones', 'linkers',
        'nanocompartments', 'ncs', 'ncsCombined', 'ncsStatus', 'promoters', 'surfaceMarkers', 'targetingPeptides',
    ]
    assert [m['id'] for m in libraries['surfaceMarkers']] == ['spycatcher', 'spytag']
    assert [nc['id'] for nc in libraries['nanocompartments']] == ['tmari', 'mxan', 'qther', 'mvp']


def test_json_cli_validates_cargo_without_failing():
    # An invalid sequence is a valid answer with ok:false,
    # not an error exit; otherwise the API would wrongly turn it into HTTP 500.
    result = _run_cli('validate', {'cargoSeq': 'ATGAAATTTGAA'})
    response = json.loads(result.stdout)

    assert result.returncode == 0
    assert response['ok'] is True
    assert response['validation']['ok'] is False
    assert 'Sequence too short' in response['validation']['errors'][0]


def test_json_cli_reports_the_real_error_on_stdout():
    # cli.py exits with 1 but puts the message on stdout. The
    # other side has to read stdout, otherwise the reason is lost.
    result = _run_cli('design', {'nanocompartment': 'doesnotexist', 'cargoSeq': CARGO})
    response = json.loads(result.stdout)

    assert result.returncode == 1
    assert response['ok'] is False
    assert 'doesnotexist' in response['error']
    assert result.stderr.strip() == ''


def test_the_stop_codon_sits_behind_the_last_coding_part_of_each_orf():
    # Cargo module (read Type 0.5 -> 0.1): the linker at 0.2 is the last coding part behind the cargo when 0.1 is an NCS spacer.
    module = _design(cargo_slots={'1': {'kind': 'ncs'}, '2': {'kind': 'linker', 'id': 'GSSS2'}})['level0']['cargoModule']
    assert [p['stop'] for p in module] == [False, True, False, False, False]
    # A targeting peptide at 0.1 is the last part of the cargo ORF (C-terminal); at 0.5 it is the first (N-terminal), the cargo ends it.
    assert [p['stop'] for p in _design(cargo_slots=CARGO_SLOTS_C_TERM)['level0']['cargoModule']] == [True, False, False, False, False]
    assert [p['stop'] for p in _design(cargo_slots=CARGO_SLOTS_N_TERM)['level0']['cargoModule']] == [False, False, True, False, False]
    # NC module: with a linker at 0.4 behind the shell and an NCS at 0.5, the stop sits behind the linker.
    nc_module = _design(nc_slots={'4': {'kind': 'linker', 'id': 'GSSS2'}, '5': {'kind': 'ncs'}})['level0']['ncModule']
    assert [p['stop'] for p in nc_module] == [False, False, False, True, False]


def test_surface_marker_sits_at_the_chosen_terminus():
    # A marker (or any other CDS) in Type 0.1/0.5 requires a linker
    # in the neighbouring slot (0.2/0.4); unlike earlier there is no automatic L1 linker
    # any more, the choice is up to the user.
    n_term = _design(nc_slots={'1': {'kind': 'marker', 'id': 'spycatcher'}, '2': {'kind': 'linker', 'id': 'GSSS2'}})['level0']['ncModule']
    c_term = _design(nc_slots={'4': {'kind': 'linker', 'id': 'GSSS2'}, '5': {'kind': 'marker', 'id': 'spycatcher'}})['level0']['ncModule']

    assert n_term[0]['kind'] == 'mark' and n_term[1]['role'] == 'nc-linker'
    assert c_term[4]['kind'] == 'mark' and c_term[3]['role'] == 'nc-linker'
    assert sum(p['stop'] for p in n_term) == 1 and sum(p['stop'] for p in c_term) == 1
    assert c_term[4]['stop'] and n_term[2]['stop']                                   # NC module: the marker at 0.5 ends the ORF; with the marker at 0.1 the shell does


def test_without_a_marker_the_slots_stay_inert_spacers():
    nc_module = _design()['level0']['ncModule']

    assert [p['role'] for p in nc_module] == ['ncs', 'ncs', 'shell', 'ncs', 'ncs']
    assert [p['stop'] for p in nc_module] == [False, False, True, False, False]     # only the shell is coding: it gets start and stop


def test_unknown_surface_marker_is_rejected():
    try:
        _design(nc_slots={'1': {'kind': 'marker', 'id': 'doesnotexist'}, '2': {'kind': 'linker', 'id': 'GSSS2'}})
    except ValueError as error:
        assert 'doesnotexist' in str(error)
    else:
        raise AssertionError('unknown marker should raise')


ADAPTER_IDS = ['0.1', '0.1rc', '0.2', '0.3', '0.4', '0.5', '0.5rc', '0.12', '0.12rc', '0.45', '0.45rc']   # the last four are the combined NCS adapters


def test_all_type_overhang_adapters_are_in_the_database():
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
    # Cargo (always) + own cargo module sequence (Type 0.1 -> rc adapter) + own NC sequence (Type 0.5 -> 0.5)
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

    # Cargo module parts are inserted as a reverse complement, NC parts unchanged
    assert constructs['GFP']['insert']['sequence'] == design['cargo']['sequence']      # shown in its own reading direction
    assert translate(constructs['Part B']['insert']['sequence']) == translate('ATG' + 'CCC' * 10) + '*'   # codon-optimized, same protein, stop added (last part of the ORF)
    assert constructs['Part A']['insert']['sequence'][-3:] in ('TAA', 'TAG', 'TGA') and constructs['GFP']['insert']['sequence'][-3:] not in ('TAA', 'TAG', 'TGA')
    for c in constructs.values():
        assert c['sequence'].startswith('GAAGAC') and c['sequence'].endswith('GTCTTC')
        assert c['insert']['sequence'] in c['sequence']
        i0, i1 = map(int, c['insert']['location'].split('..'))
        assert c['sequence'][i0 - 1:i1] == c['insert']['sequence']

    genbank = build_genbank(design)
    assert 'LOCUS       Level0.1_Part-A_Cargo' in genbank
    assert 'with-overhangs' not in genbank
    assert genbank.count('//') == genbank.count('LOCUS')


def test_every_module_gets_a_level0_construct_and_only_user_input_is_flagged():
    design = _design()
    constructs = design['level0Constructs']
    assert [(c['module'], c['slot']) for c in constructs] == \
        [('cargo_site', n) for n in range(1, 6)] + [('nc_site', n) for n in range(1, 6)]
    assert [c['adapter'] for c in constructs] == ['0.1rc', '0.2', '0.3', '0.4', '0.5rc', '0.1', '0.2', '0.3', '0.4', '0.5']
    assert [c['label'] for c in constructs if c['isUser']] == ['GFP']
    # every toolkit part used here has a real insert in the parts database
    assert all(c['isReal'] for c in constructs)


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
    assert sorted(design) == ['cargo', 'cargoSlots', 'codonOptimization', 'level0', 'level0Constructs', 'level1Constructs', 'level2',
                              'level2Construct', 'nanocompartment', 'ncSlots', 'primers', 'targetingPeptide']
    assert sorted(design['cargo']) == ['bp', 'label', 'sequence', 'sequenceAntisense']
    assert sorted(design['level2']['promoter']) == ['bp', 'id', 'label']


def _long_cargo():
    import random
    rng = random.Random(7)
    codons = [a + b + c for a in 'ACGT' for b in 'ACGT' for c in 'ACGT' if a + b + c not in ('TAA', 'TAG', 'TGA')]
    seq = 'ATG' + ''.join(rng.choice(codons) for _ in range(200))
    return seq


def test_level0_primers_carry_the_adapter_flanks_and_anneal_to_the_insert():
    cds = _long_cargo()
    design = _design(cargoSeq=cds)
    construct = next(c for c in design['level0Constructs'] if c['module'] == 'cargo_site' and c['slot'] == 3)
    pr = construct['primers']
    assert pr['possible'] is True

    start, end = location_span(construct['insert']['location'])
    flank5, flank3 = construct['sequence'][:start - 1], construct['sequence'][end:]
    insert = construct['insert']['sequence']
    assert translate(insert) == translate(cds)            # the cargo site is shown in reading direction (codon-optimized, same protein)
    fwd, rev = pr['forward'], pr['reverse']
    assert fwd['sequence'] == pr['clamp'] + flank5 + fwd['anneal']
    assert insert.startswith(fwd['anneal'])
    assert rev['sequence'] == pr['clamp'] + reverse_complement(flank3) + rev['anneal']
    assert insert.endswith(reverse_complement(rev['anneal']))
    # PCR product = construct + one clamp on each side
    assert pr['productLength'] == construct['length'] + 2 * len(pr['clamp'])
    # BbsI recognition site lies behind the clamp, so that the enzyme cuts at the end of the product
    assert fwd['sequence'][len(pr['clamp']):].startswith('GAAGAC')
    assert rev['sequence'][len(pr['clamp']):].startswith('GAAGAC')
    assert pr['internalSites'] == [] or all('site' in s for s in pr['internalSites'])
    assert '/label="%s"' % fwd['name'] in construct['genbank']
    assert '/label="%s"' % rev['name'] in construct['genbank']
    assert 'primer_bind' in construct['genbank']


def test_level0_primers_need_a_real_long_enough_insert(monkeypatch):
    import Biologik.level0_design.constructs as constructs_module
    import Biologik.level0_design.parts_db as parts_db_module
    monkeypatch.setattr(constructs_module, 'find_inserts', lambda *args, **kwargs: [])      # no inserts -> placeholders
    monkeypatch.setattr(parts_db_module, 'find_inserts', lambda *args, **kwargs: [])
    design = _design(cargoSeq=_long_cargo())
    placeholder = next(c for c in design['level0Constructs'] if not c['isReal'])
    assert placeholder['primers']['possible'] is False
    assert 'real sequence' in placeholder['primers']['reason']

    monkeypatch.undo()
    short = next(c for c in _design()['level0Constructs'] if c['module'] == 'cargo_site' and c['slot'] == 3)
    assert short['primers']['possible'] is False and 'below 150 bp' in short['primers']['reason']


def test_level0_primers_flag_internal_restriction_sites(monkeypatch):
    import Biologik.level0_design.user_codons as user_codons_module
    cds = _long_cargo()
    cds = cds[:60] + 'GAAGAC' + cds[66:]  # BbsI site in the middle of the insert
    monkeypatch.setattr(user_codons_module, 'codon_optimize_part',
                        lambda sequence, module, slot, protein=False: optimize_cds(sequence) | {'sequence': sequence, 'optimized': False})
    design = _design(cargoSeq=cds)  # without optimization the site stays, and the primers warn about it
    pr = next(c for c in design['level0Constructs'] if c['module'] == 'cargo_site' and c['slot'] == 3)['primers']
    assert any('BbsI' in s for s in pr['internalSites'])


def test_level0_primers_export_a_genbank_of_the_pcr_product():
    cds = _long_cargo()
    design = _design(cargoSeq=cds)
    construct = next(c for c in design['level0Constructs'] if c['module'] == 'cargo_site' and c['slot'] == 3)
    pr = construct['primers']
    gb = pr['genbank']
    assert gb.startswith('LOCUS') and gb.count('//') == 1 and 'linear' in gb.splitlines()[0]
    assert f"{pr['productLength']} bp" in gb.splitlines()[0]
    for primer in (pr['forward'], pr['reverse']):
        assert f'/label="{primer["name"]}"' in gb
    assert gb.count('primer_bind') == 2
    assert f"1..{pr['forward']['length']}" in gb and f"complement({pr['productLength'] - pr['reverse']['length'] + 1}..{pr['productLength']})" in gb
    # is also part of the complete GenBank export
    full = build_genbank(design)
    assert 'LOCUS       Level0.3_Primers_GFP_Cargo' in full
    assert 'LOCUS       Level0.3_GFP_Cargo' in full


def test_record_names_tell_the_site_without_reading_the_description():
    design = _design(cargoSeq=_long_cargo())
    names = {(c['module'], c['slot']): c['genbank'].splitlines()[0].split()[1] for c in design['level0Constructs']}
    assert names[('cargo_site', 3)] == 'Level0.3_GFP_Cargo'
    assert names[('nc_site', 3)] == 'Level0.3_E-Tm_NC'
    assert names[('cargo_site', 2)].startswith('Level0.2_') and names[('cargo_site', 2)].endswith('_Cargo') and names[('nc_site', 2)].startswith('Level0.2_') and names[('nc_site', 2)].endswith('_NC')
    assert len(set(names.values())) == 10

    cargo = next(c for c in design['level0Constructs'] if c['module'] == 'cargo_site' and c['slot'] == 3)
    assert cargo['primers']['genbank'].splitlines()[0].split()[1] == 'Level0.3_Primers_GFP_Cargo'
    assert cargo['primers']['forward']['name'] == 'Level0.3_GFP_Cargo_F'
    assert cargo['primers']['reverse']['name'] == 'Level0.3_GFP_Cargo_R'


# ---------------------------------------------------------------------------------------------------------
# Level 1 (BsaI) and Level 2 (BbsI): the assemblies are really recomputed here as a "digest".

def _bsai_fragment(plasmid: str) -> str:
    """Top strand fragment that BsaI cuts out of a Level 0 plasmid (pieces between the two cuts)."""
    left = plasmid.index('GGTCTC')  # top strand site, cuts 1 nt behind it, overhang = 4 nt
    right = plasmid.index('GAGACC')  # site on the opposite strand, cuts 1 nt before it
    return plasmid[left + 7:right - 1]


def _bbsi_piece(plasmid: dict) -> str:
    """Top strand piece between the two BbsI cuts of the Level 1 plasmid: 2 nt behind GAAGAC and 2 nt before
        GTCTTC, each with a 4-nt overhang. The two sites are those of the backbone left/right of the insert."""
    seq = plasmid['sequence']
    left = 2                                                # GAAGAC an 3..8
    right = plasmid['insertEnd'] - 2  # GTCTTC starts at the G of TTGT
    assert seq.startswith('GAAGAC', left) and seq.startswith('GTCTTC', right)
    return seq[left + 8:right - 2]


def _real_design():
    return _design(cargoSeq=_long_cargo(), nc_slots={'4': {'kind': 'custom', 'label': 'MyPart', 'seq': 'ATG' + 'GCT' * 20}})


def test_level1_modules_are_the_bsai_assembly_of_the_level0_parts():
    design = _real_design()
    cargo, promoter, nc = design['level1Constructs']
    assert [m['name'] for m in (cargo, promoter, nc)] == ['Level1_Cargo', 'Level1_Promoter', 'Level1_NC']
    for m in (cargo, promoter, nc):
        assert m['sequence'].startswith('ACAT') and m['sequence'].endswith('TTGT')        # NLvl1 / CLvl1 of pAGM1311
    assert cargo['level2Overhangs'] == {'n': 'CCAA', 'c': 'CGTT'}
    assert promoter['level2Overhangs'] == {'n': 'CGTT', 'c': 'TGAT'}
    assert nc['level2Overhangs'] == {'n': 'TGAT', 'c': 'AATG'}

    # The five fragments that BsaI cuts out of the real Level 0 plasmids give exactly the module.
    for module, site in ((cargo, 'cargo_site'), (nc, 'nc_site')):
        pieces = [_bsai_fragment(c['plasmid']['sequence']) for c in design['level0Constructs'] if c['module'] == site]
        assembled = pieces[0]
        for piece in pieces[1:]:
            assert assembled[-4:] == piece[:4]
            assembled += piece[4:]
        assert assembled == module['sequence']
    junctions = [o['sequence'] for o in cargo['overhangs'] if o['label'].startswith('0.')]
    assert 'TATG' in junctions and 'TTCT' in junctions and 'ATCC' in junctions and 'TGGC' in junctions


def test_level1_parts_sit_where_their_features_say():
    design = _real_design()
    cargo, _, nc = design['level1Constructs']
    gene = next(p for p in cargo['parts'] if p['label'] == 'GFP')
    # The cargo module lies as a reverse complement on the top strand (antisense).
    assert gene['strand'] == 'antisense'
    assert cargo['sequence'][gene['start'] - 1:gene['end']] == reverse_complement(design['cargo']['sequence'])
    mine = next(p for p in nc['parts'] if p['label'] == 'MyPart')
    assert mine['strand'] == 'sense' and translate(nc['sequence'][mine['start'] - 1:mine['end']]).rstrip('*') == translate('ATG' + 'GCT' * 20)
    assert 'complement(' in cargo['genbank'] and '/label="GFP"' in cargo['genbank']


def test_level1_plasmid_has_the_module_between_bbsi_sites_and_no_bsai_site():
    design = _real_design()
    backbone = next(iter(load_parts()['level1_backbones']))
    cargo = design['level1Constructs'][0]
    pl = cargo['plasmid']
    assert pl['length'] == backbone['length_bp'] - (606 - 7 + 1) + cargo['length']
    seq = pl['sequence']
    assert seq[pl['insertStart'] - 1:pl['insertEnd']] == cargo['sequence']
    assert seq.count('GGTCTC') + seq.count('GAGACC') == 0                       # BsaI sites are cut away with the stuffer
    assert seq[2:8] == 'GAAGAC' and seq[:pl['insertStart'] - 1] == backbone['sequence'][:pl['insertStart'] - 1]
    assert seq.endswith(backbone['sequence'][-100:])
    assert '/label="KanR"' in pl['genbank'] and '/label="0.1N Lvl1"' in pl['genbank']
    # BbsI cuts exactly the piece between the Level 2 overhangs out of the plasmid
    assert _bbsi_piece(pl) == cargo['sequence'][4:-4]


def test_level2_is_the_bbsi_assembly_of_the_three_level1_modules():
    design = _real_design()
    cargo, promoter, nc = design['level1Constructs']
    level2 = design['level2Construct']
    pieces = [_bbsi_piece(m['plasmid']) for m in (cargo, promoter, nc)]
    assembled = pieces[0]
    for piece in pieces[1:]:
        assert assembled[-4:] == piece[:4]
        assembled += piece[4:]
    assert assembled == level2['sequence']
    assert level2['junctions'] == {'n': 'CCAA', 'cargoPromoter': 'CGTT', 'promoterNc': 'TGAT', 'c': 'AATG'}

    backbone = next(iter(load_parts()['level2_backbones']))
    pl = level2['plasmid']
    assert pl['length'] == backbone['length_bp'] - 824 + level2['length']
    assert pl['sequence'][pl['insertStart'] - 1:pl['insertEnd']] == level2['sequence']
    assert pl['sequence'].startswith(backbone['sequence'][:2126] + 'CCAA')
    assert pl['sequence'][pl['insertEnd'] - 4:pl['insertEnd']] == 'AATG' and pl['sequence'][pl['insertEnd']:pl['insertEnd'] + 20] == backbone['sequence'][2950:2970]
    for label in ('HIS3', 'AmpR', 'ADH1 terminator', 'CYC1 terminator', 'GFP', 'BbLvl2N', 'BbLvl2C'):
        assert f'/label="{label}"' in pl['genbank']
    assert 'BbsI Rec Site' not in pl['genbank']                       # the cassette's own BbsI sites are gone


def test_internal_restriction_sites_are_reported_on_level1(monkeypatch):
    import Biologik.level0_design.user_codons as user_codons_module
    cds = _long_cargo()
    cds = cds[:60] + 'GGTCTC' + cds[66:]
    monkeypatch.setattr(user_codons_module, 'codon_optimize_part',
                        lambda sequence, module, slot, protein=False: optimize_cds(sequence) | {'sequence': sequence, 'optimized': False})
    cargo = _design(cargoSeq=cds)['level1Constructs'][0]  # without optimization the site stays
    assert any('BsaI' in s and 'GFP' in s for s in cargo['internalSites'])


def test_libraries_ship_level1_and_level2_backbones_with_a_ready_genbank_text():
    from Biologik.level0_design.data import get_libraries
    libs = get_libraries()
    for key, name, bp, labels in (('level1Backbones', 'pAGM1311', 2621, ('KanR', 'ori', 'lacZ-alpha', 'BbsI rec site', 'BsaI rec site')),
                                  ('level2Backbones', 'pESC', 6543, ('HIS3', 'AmpR', 'ADH1 terminator', 'CYC1 terminator'))):
        gb = libs[key][0]['genbank']
        assert gb.startswith(f'LOCUS       {name}') and f'{bp} bp' in gb and 'circular' in gb and gb.count('LOCUS') == 1 and gb.strip().endswith('//')
        for label in labels:
            assert f'/label="{label}"' in gb


def test_level0_plasmid_names_are_unique_and_tell_type_and_site():
    design = _design(cargoSeq=_long_cargo())
    names = [c['plasmid']['name'] for c in design['level0Constructs']]
    assert len(set(names)) == 10
    assert 'pAGM9121_Level0.3_GFP_Cargo' in names and 'pAGM9121_Level0.2_NCS_NC' in names
    assert all(c['plasmid']['genbank'].startswith('LOCUS       ' + c['plasmid']['name']) for c in design['level0Constructs'])


def test_cargo_module_is_shown_rotated_so_the_cargo_reads_5_to_3_left_to_right():
    design = _real_design()
    cargo, promoter, nc = design['level1Constructs']
    shown = cargo['shown']
    assert shown['sequence'] == reverse_complement(cargo['sequence'])
    assert [p['label'] for p in shown['parts']][0] == 'NCS' and [p['label'] for p in shown['parts']][-1] == 'TP-Tm'     # Type 0.5 ... 0.1
    gene = next(p for p in shown['parts'] if p['label'] == 'GFP')
    assert gene['strand'] == 'sense' and shown['sequence'][gene['start'] - 1:gene['end']] == design['cargo']['sequence']
    assert shown['level2Overhangs'] == {'n': reverse_complement('CGTT'), 'c': reverse_complement('CCAA')}
    assert shown['sequence'][:4] == reverse_complement('TTGT') and shown['sequence'][-4:] == reverse_complement('ACAT')
    assert 'complement(' not in shown['genbank'] and '/label="GFP"' in shown['genbank']
    # NC module and promoter stay unchanged; plasmid and Level 2 continue to work with the top strand orientation
    assert promoter['shown'] is None and nc['shown'] is None
    assert cargo['plasmid']['sequence'][cargo['plasmid']['insertStart'] - 1:cargo['plasmid']['insertEnd']] == cargo['sequence']
    assert shown['genbank'] in build_genbank(design)


# ---------------------------------------------------------------------------------------------------------
# Reading frame: 2-nt frame spacer directly before the insert of every adapter (parts/type_overhangs/)

def _orf_codons(sequence: str) -> list:
    return [sequence[i:i + 3] for i in range(0, len(sequence), 3)]


def _frame_design():
    import random
    rng = random.Random(5)
    codons = [a + b + c for a in 'ACGT' for b in 'ACGT' for c in 'ACGT' if a + b + c not in ('TAA', 'TAG', 'TGA')]

    def cds(n):
        return 'ATG' + ''.join(rng.choice(codons) for _ in range(n))

    parts = {'cargo': cds(100), 'A': cds(10), 'B': cds(14), 'C': cds(20), 'D': cds(8)}
    design = design_construct({
        'nanocompartment': 'tmari', 'cargoSeq': parts['cargo'], 'cargoLabel': 'G',
        'cargoSlots': {'1': {'kind': 'custom', 'label': 'A', 'seq': parts['A']}, '2': {'kind': 'custom', 'label': 'B', 'seq': parts['B']}},
        'ncSlots': {'4': {'kind': 'custom', 'label': 'C', 'seq': parts['C']}, '5': {'kind': 'custom', 'label': 'D', 'seq': parts['D']}},
    })
    return design, parts


def test_every_adapter_carries_a_two_base_frame_spacer_directly_before_the_insert():
    for adapter in load_parts()['type_overhangs']:
        sp = adapter['frame_spacer']
        a, b = location_span(sp['location'])
        i0, _ = location_span(adapter['insert']['location'])
        assert b - a + 1 == 2 and b + 1 == i0                                       # directly 5' of the insert
        assert adapter['sequence'][a - 1:b] == sp['sequence'] == 'GC'
        assert adapter['length_bp'] == len(adapter['sequence'])
        # the spacer lies behind the Level 1 N overhang and before the Level 1 C overhang -> inside the BsaI fragment
        n0, _ = location_span(next(o for o in adapter['overhangs'] if o['role'] == 'level1_N')['location'])
        c0, _ = location_span(next(o for o in adapter['overhangs'] if o['role'] == 'level1_C')['location'])
        assert n0 < a and b < c0


def test_fused_parts_stay_in_frame_in_both_modules_and_in_the_final_plasmid():
    design, parts = _frame_design()
    cargo_module, _, nc_module = design['level1Constructs']

    # every junction between two parts is overhang (4) + spacer (2) = 6 nt -> a multiple of 3
    for module in (cargo_module, nc_module):
        for left, right in zip(module['parts'], module['parts'][1:]):
            assert (right['start'] - left['end'] - 1) == 6

    # cargo ORF (antisense module, read in the rotated view): cargo -> B -> A, multiple of 3, only the added stop codon at the very end
    shown = cargo_module['shown']
    ps = {p['label']: p for p in shown['parts']}
    orf = shown['sequence'][ps['G']['start'] - 1:ps['A']['end']]
    assert len(orf) == len(parts['cargo']) + len(parts['B']) + len(parts['A']) + 12 + 3 and len(orf) % 3 == 0
    assert not {'TAA', 'TAG', 'TGA'} & set(_orf_codons(orf)[:-1]) and _orf_codons(orf)[-1] == 'TAA'

    cargo_orf = orf
    # NC ORF: C -> D
    ps = {p['label']: p for p in nc_module['parts']}
    nc_orf = nc_module['sequence'][ps['C']['start'] - 1:ps['D']['end']]
    assert len(nc_orf) == len(parts['C']) + len(parts['D']) + 6 + 3 and len(nc_orf) % 3 == 0
    assert not {'TAA', 'TAG', 'TGA'} & set(_orf_codons(nc_orf)[:-1]) and _orf_codons(nc_orf)[-1] == 'TAA'

    # the same ORFs sit unchanged in the finished Level 2 plasmid: NC on the top strand, cargo as reverse complement
    plasmid = design['level2Construct']['plasmid']['sequence']
    assert nc_orf in plasmid and reverse_complement(cargo_orf) in plasmid


def test_junction_codons_are_never_stops_in_either_reading_direction():
    for adapter in load_parts()['type_overhangs']:
        n = next(o for o in adapter['overhangs'] if o['role'] == 'level1_N')['sequence_top_strand']
        six = n + adapter['frame_spacer']['sequence']
        for reading in (six, reverse_complement(six)):
            assert not {'TAA', 'TAG', 'TGA'} & set(_orf_codons(reading)), (adapter['id'], reading)


def test_frame_spacers_are_annotated_in_constructs_and_plasmids():
    design, _ = _frame_design()
    for construct in design['level0Constructs']:
        # the cargo Type 0.5 is the first part in reading direction: nothing precedes it, so it carries no spacer
        has_spacer = not (construct['module'] == 'cargo_site' and construct['slot'] == 5)
        assert ('/label="Frame spacer"' in construct['genbank']) == has_spacer
        assert ('/label="Frame spacer"' in construct['plasmid']['genbank']) == has_spacer
    cargo_module, _, nc_module = design['level1Constructs']
    assert cargo_module['genbank'].count('/label="Frame spacer"') == 4 and cargo_module['plasmid']['genbank'].count('/label="Frame spacer"') == 4
    assert nc_module['genbank'].count('/label="Frame spacer"') == 5 and nc_module['plasmid']['genbank'].count('/label="Frame spacer"') == 5
    assert cargo_module['shown']['genbank'].count('/label="Frame spacer"') == 4
    assert design['level2Construct']['plasmid']['genbank'].count('/label="Frame spacer"') == 9


def test_cargo_spacer_sits_behind_the_part_on_the_plasmid_top_strand_and_follows_the_overhang_in_reading_direction():
    design, _ = _frame_design()
    cargo_module, _, nc_module = design['level1Constructs']
    top = cargo_module['sequence']                                         # plasmid top strand: Type 0.1 ... 0.5 left to right
    parts = cargo_module['parts']
    for left, right in zip(parts, parts[1:]):
        gap = top[left['end']:right['start'] - 1]                          # between two parts: spacer, then overhang
        assert gap[:2] == 'GC' and len(gap) == 6
    shown = cargo_module['shown']
    for left, right in zip(shown['parts'], shown['parts'][1:]):            # reading direction: overhang, then spacer
        assert shown['sequence'][left['end']:right['start'] - 1][-2:] == 'GC'
    nc = nc_module['sequence']
    for left, right in zip(nc_module['parts'], nc_module['parts'][1:]):
        assert nc[left['end']:right['start'] - 1][-2:] == 'GC'


# ---------------------------------------------------------------------------------------------------------
# Ordering: oligos for parts that are too short

def test_short_real_parts_get_an_oligo_pair_that_anneals_to_the_bbsi_cut_fragment():
    short = 'ATG' + 'GCT' * 5
    design = _design(cargoSeq=_long_cargo(), nc_slots={'4': {'kind': 'custom', 'label': 'Tiny', 'seq': short}})
    tiny = next(c for c in design['level0Constructs'] if c['label'] == 'Tiny')
    assert tiny['primers']['possible'] is False and tiny['isReal'] and tiny['isUser']
    o = tiny['oligos']
    assert o['possible'] and o['top']['name'] == 'Level0.4_Oligo_Tiny_NC_F' and o['bottom']['name'] == 'Level0.4_Oligo_Tiny_NC_R'
    # top = 0N overhang + ds part, bottom = reverse complement of everything after 0N up to and including 0C
    assert o['overhangs'] == {'left': 'CTCA', 'right': 'CTCG'}
    pl = tiny['plasmid']
    fragment = pl['sequence'][pl['insertStart'] - 1:pl['insertEnd']]                     # what BbsI leaves between the backbone overhangs
    assert fragment == o['top']['sequence'][:4] + reverse_complement(o['bottom']['sequence'])
    assert o['top']['sequence'][4:] == reverse_complement(o['bottom']['sequence'])[:-4]   # the two strands are complementary
    assert tiny['insert']['sequence'] in fragment and translate(tiny['insert']['sequence']) == translate(short) + '*'   # + stop (last part of the ORF)

    # real parts long enough for primers, and placeholders, get no oligos
    gene = next(c for c in design['level0Constructs'] if c['label'] == 'GFP')
    assert gene['oligos'] is None and gene['primers']['possible']
    assert all(c['oligos'] is None for c in design['level0Constructs'] if not c['isReal'])


def test_toolkit_constructs_carry_the_registry_link_of_their_part_and_own_sequences_never_do():
    design = _design(cargoSeq=_long_cargo(), nc_slots={'4': {'kind': 'custom', 'label': 'Mine', 'seq': 'ATG' + 'GCT' * 20}})
    by_slot = {(c['module'], c['slot']): c for c in design['level0Constructs']}
    assert all('registryUrl' in c and 'onStock' not in c and 'plasmid_source' not in c for c in by_slot.values())
    assert by_slot[('nc_site', 3)]['registryUrl'] == 'https://registry.igem.org/parts/bba-261v56af'        # E-Tm shell
    assert by_slot[('nc_site', 1)]['registryUrl'] == 'https://registry.igem.org/parts/bba-26m21ryz'        # NCS
    assert by_slot[('nc_site', 4)]['registryUrl'] is None and by_slot[('cargo_site', 3)]['registryUrl'] is None   # own sequences: never
    # a toolkit part that has no Registry entry yet keeps the placeholder (no URL)
    gsss2 = _design(nc_slots={'4': {'kind': 'linker', 'id': 'GSSS2'}})['level0Constructs']
    assert next(c for c in gsss2 if c['module'] == 'nc_site' and c['slot'] == 4)['registryUrl'] is None


def test_every_level0_insert_in_the_database_has_a_registry_url_field():
    from Biologik.level0_design.parts_db import inserts
    assert all('registry_url' in e for e in inserts())


# ---------------------------------------------------------------------------------------------------------
# Level 0 inserts database (parts/level0_inserts/): bare part sequences from the Level 0 plasmids

def test_insert_database_is_consistent():
    from Biologik.level0_design.parts_db import bare_cds, inserts
    entries = inserts()
    assert len(entries) == 58                                                  # 37 plasmids from GenBank + 21 listed for completeness (no internal id)
    for e in entries:
        assert set(e['sequence']) <= set('ACGT') and e['length_bp'] == len(e['sequence'])
        assert e['site'] in ('nc_site', 'cargo_site') and e['stored_orientation'] in ('sense', 'antisense')
        # no overhang / spacer bases and no domestication problems left in the stored part
        assert e['checks']['bsai_sites'] == [] and e['checks']['bbsi_sites'] == []
        # the site follows the Level 2 overhang (Type 0.1 / 0.5) or the strand the part is stored on (Types 0.2-0.4)
        if e['level2_overhang'] in ('TGAT', 'AATG'):
            assert e['site'] == 'nc_site' and e['stored_orientation'] == 'sense'
        elif e['level2_overhang'] in ('CCAA', 'CGTT'):
            assert e['site'] == 'cargo_site' and e['stored_orientation'] == 'antisense'
        if e['category'] == 'shell':
            assert e['site'] == 'nc_site' and e['type_slot'] == 3
        if e['category'] == 'cargo':
            assert e['type_slot'] == 3                                        
    ids = [e['id'] for e in entries if e['id']]                               # plasmids that are not built have no id
    assert len(set(ids)) == len(ids)
    # coding parts are stored bare (no start codon, no stop codon at the end; the software adds both per slot) and are a multiple of 3
    coding = [e for e in entries if e['category'] in ('shell', 'cargo', 'linker', 'tp', 'marker', 'intein')]
    assert all(bare_cds(e['sequence']) == e['sequence'] for e in coding if e['category'] != 'linker')
    assert [e['id'] for e in coding if len(e['sequence']) % 3] == []
    # one file per part: all plasmids of a part share its sequence; there is exactly one NCS sequence for every NCS plasmid
    for part in load_parts()['level0_inserts']:
        assert part['plasmids'] and 'sequence' in part
    assert {e['sequence'] for e in entries if e['category'] == 'ncs'} == {'CCGTCAGGGCGCGTCAGCGGGTGTTGGCGGGTGTCGGGG'}


def test_libraries_offer_each_part_only_where_a_level0_plasmid_exists():
    from Biologik.level0_design.data import get_libraries
    libs = get_libraries()
    linkers = {l['id']: l['slots'] for l in libs['linkers']}
    assert linkers == {'GGS2': {'nc': [2, 4], 'cargo': [2, 4]}, 'GSSS2': {'nc': [2, 4], 'cargo': [2, 4]},
                       'GSSS3': {'nc': [2, 4], 'cargo': [2, 4]}, 'GSSS4': {'nc': [2, 4], 'cargo': [2, 4]}}
    assert {m['id']: m['slots'] for m in libs['surfaceMarkers']} == {'spycatcher': {'nc': [1, 5], 'cargo': [1, 5]}, 'spytag': {'nc': [1, 5], 'cargo': [1, 5]}}
    assert libs['inteins'][0]['slots'] == {'nc': [1, 5], 'cargo': [1, 5]}
    assert all(t['slots'] == {'nc': [], 'cargo': [1, 5]} for t in libs['targetingPeptides'])
    # NCS: one plain spacer at every slot of both sites (no NCS with stop codon: the stop is added behind the last coding part)
    assert libs['ncs'] == {'nc': {'1': ['plain'], '2': ['plain'], '4': ['plain'], '5': ['plain']},
                           'cargo': {'1': ['plain'], '2': ['plain'], '4': ['plain'], '5': ['plain']}}
    assert [c['id'] for c in libs['cargoPresets']] == ['yegfp', 'lgb4', 'nlucp', 'civcpo', 'pabp', 'pabp-rrm1-4', 'pabp-rrm1-2']
    assert [n['shellBp'] for n in libs['nanocompartments']] == [798, 864, 849, 2682]


def test_a_cargo_taken_unchanged_from_the_library_is_a_toolkit_part():
    from Biologik.level0_design.data import get_libraries
    yegfp = next(c for c in get_libraries()['cargoPresets'] if c['id'] == 'yegfp')
    design = _design(cargoSeq=yegfp['seq'], cargoLabel='yeGFP')
    cargo = next(c for c in design['level0Constructs'] if c['module'] == 'cargo_site' and c['slot'] == 3)
    assert cargo['isUser'] is False and cargo['what'] == 'cargo (toolkit part)'
    edited = _design(cargoSeq=yegfp['seq'][:-3] + 'GCT', cargoLabel='yeGFP')
    mine = next(c for c in edited['level0Constructs'] if c['module'] == 'cargo_site' and c['slot'] == 3)
    assert mine['isUser'] is True


def test_toolkit_parts_use_the_inserts_of_their_own_site_and_slot():
    design = _design(cargoSeq=_long_cargo(), cargo_slots={'1': {'kind': 'ncs'}, '2': {'kind': 'ncs'}, '4': {'kind': 'linker', 'id': 'GSSS3'}, '5': {'kind': 'tp'}},
                     nc_slots={'1': {'kind': 'marker', 'id': 'spycatcher'}, '2': {'kind': 'linker', 'id': 'GSSS2'}, '4': {'kind': 'ncs'}})
    by = {(c['module'], c['slot']): c for c in design['level0Constructs']}
    # the cargo module sits antisense: its linker is the reverse complement of the sense insert in the DB
    from Biologik.level0_design.parts_db import find_inserts
    gsss3 = find_inserts('linker', 'GSSS3', 'cargo_site', 4)[0]['sequence']
    assert by[('cargo_site', 4)]['insert']['sequence'] == gsss3                       # shown rotated -> sense again
    assert by[('nc_site', 1)]['insert']['sequence'] == 'ATG' + find_inserts('marker', 'spycatcher')[0]['sequence']   # first part of the ORF: start added
    assert by[('nc_site', 4)]['insert']['sequence'] == find_inserts('ncs', 'ncs', 'nc_site', 4)[0]['sequence']
    assert by[('nc_site', 4)]['insert']['sequence'] == 'CCGTCAGGGCGCGTCAGCGGGTGTTGGCGGGTGTCGGGG'     # the one NCS sequence, no stop codon
    assert by[('cargo_site', 5)]['insert']['sequence'] == 'ATG' + find_inserts('tp', 'TP-Tm', 'cargo_site', 5)[0]['sequence']


def test_a_custom_nanocompartment_has_no_targeting_peptide():
    shell = 'ATG' + 'GCT' * 30
    design = _design(nanocompartment='custom', customNanocompartment={'label': 'MyShell', 'seq': shell},
                     cargo_slots={'1': {'kind': 'custom', 'label': 'MyTP', 'seq': 'ATG' + 'GCT' * 4}, '2': {'kind': 'linker', 'id': 'GSSS2'}})
    assert design['targetingPeptide'] is None and design['nanocompartment']['custom'] is True
    with pytest.raises(ValueError, match='no targeting peptide'):
        _design(nanocompartment='custom', customNanocompartment={'label': 'MyShell', 'seq': shell},
                cargo_slots={'1': {'kind': 'tp'}, '2': {'kind': 'linker', 'id': 'GSSS2'}})


def test_primers_exist_only_for_own_sequences_of_at_least_150_bp_and_shorter_parts_become_oligos():
    design = _design(cargoSeq=_long_cargo(), nc_slots={'4': {'kind': 'custom', 'label': 'Mid', 'seq': 'ATG' + 'GCT' * 30}})
    for c in design['level0Constructs']:
        n = len(c['insert']['sequence'])
        # primers: only own sequences that are long enough for PCR
        assert c['primers']['possible'] is (c['isUser'] and n >= 150)
        # oligo pair: every part with a real sequence below 150 bp; own or toolbox, no matter which
        assert (c['oligos'] is not None) == (c['isReal'] and n < 150)
    mid = next(c for c in design['level0Constructs'] if c['label'] == 'Mid')            # 93 bp own part -> oligos, no primers
    assert mid['oligos']['possible'] is True and mid['primers']['possible'] is False and 'below 150 bp' in mid['primers']['reason']
    toolkit = next(c for c in design['level0Constructs'] if not c['isUser'] and len(c['insert']['sequence']) >= 150)
    assert 'only designed for your own sequences' in toolkit['primers']['reason'] and toolkit['oligos'] is None   # the shell
    ncs = [c for c in design['level0Constructs'] if c['label'] == 'NCS']
    assert ncs and all(c['oligos'] and c['oligos']['possible'] for c in ncs)



def test_the_part_that_ends_the_orf_is_flagged_and_ncs_spacers_never_are():
    design = _design(cargoSeq=_long_cargo(), nc_slots={'4': {'kind': 'linker', 'id': 'GSSS2'}})
    flags = {(c['module'], c['slot']): c['stopCodon'] for c in design['level0Constructs']}
    assert flags[('nc_site', 4)] is True and flags[('nc_site', 3)] is False and flags[('nc_site', 5)] is False
    assert all(not c['stopCodon'] for c in design['level0Constructs'] if c['label'] == 'NCS')


def test_the_stop_codon_is_marked_in_construct_oligos_and_plasmid():
    design = _design(cargoSeq=_long_cargo(), cargo_slots={'1': {'kind': 'ncs'}, '2': {'kind': 'linker', 'id': 'GSSS2'}},
                     nc_slots={'4': {'kind': 'linker', 'id': 'GSSS2'}})
    stops = {'TAA', 'TAG', 'TGA'}
    for module, slot in (('nc_site', 4), ('cargo_site', 2)):
        c = next(c for c in design['level0Constructs'] if c['module'] == module and c['slot'] == slot)
        a, b = location_span(c['stopLocation'])
        assert c['sequence'][a - 1:b] in stops                                    # shown in reading direction
        assert '/label="Stop codon"' in c['genbank'] and '/label="Stop codon"' in c['plasmid']['genbank']
        o = c['oligos']['stop']
        if o['top']:
            assert c['oligos']['top']['sequence'][o['top'][0]:o['top'][1] + 1] in stops | {reverse_complement(x) for x in stops}
        if o['bottom']:
            assert c['oligos']['bottom']['sequence'][o['bottom'][0]:o['bottom'][1] + 1] in stops | {reverse_complement(x) for x in stops}
        assert o['top'] or o['bottom']
    plain = next(c for c in design['level0Constructs'] if c['module'] == 'nc_site' and c['slot'] == 5)
    assert plain['stopLocation'] is None and plain['oligos']['stop'] is None


def test_oligo_pairs_come_with_an_annotated_genbank_record_of_the_annealed_fragment():
    design = _design(cargoSeq=_long_cargo(), nc_slots={'4': {'kind': 'linker', 'id': 'GSSS2'}})
    for c in design['level0Constructs']:
        if not c['oligos']:
            continue
        gb, o = c['oligos']['genbank'], c['oligos']
        assert gb.startswith('LOCUS       ' + f"Level0.{c['slot']}_Oligos_") and gb.strip().endswith('//')
        assert gb.count('primer_bind') == 2 and f"/label=\"{o['top']['name']}\"" in gb and f"/label=\"{o['bottom']['name']}\"" in gb
        assert f"{o['annealedLength']} bp" in gb.splitlines()[0]
    stop = next(c for c in design['level0Constructs'] if c['module'] == 'nc_site' and c['slot'] == 4)
    assert '/label="Stop codon"' in stop['oligos']['genbank'] and '/label="Frame spacer"' in stop['oligos']['genbank']


# Codon optimization for S. cerevisiae: every entered sequence, protein unchanged, no BsaI/BbsI sites

SITE_CDS = ('ATG' + 'GAAGAC' + 'GGTCTC' + 'GAGACC' + 'GTCTTC' + 'AAATTTGGTCTCAAAGAAGACGAGACCCGT' * 3
            + 'TTTTTTTTTTTTTTTAAAAAAAAAAAAAAAAAA' + 'GGG' * 3)


def test_codon_optimization_keeps_the_protein_and_removes_every_bsai_and_bbsi_site():
    assert len(find_forbidden(SITE_CDS)) >= 8
    result = optimize_cds(SITE_CDS)
    assert result['status'] == 'optimized' and result['optimized']
    assert translate(result['sequence']) == translate(SITE_CDS) and len(result['sequence']) == len(SITE_CDS)
    assert find_forbidden(result['sequence']) == [] and result['forbiddenAfter'] == []
    assert len(result['forbiddenBefore']) >= 8
    assert max(len(m) for m in re.findall(r'A+|C+|G+|T+', result['sequence'])) <= 6


def test_codon_optimization_is_reproducible_and_yeast_like_like_vectorbuilder():
    cds = _long_cargo()
    a, b = optimize_cds(cds), optimize_cds(cds)
    assert a['sequence'] == b['sequence']                                   # seeded with the input
    assert translate(a['sequence']) == translate(cds)
    # VectorBuilder (S. cerevisiae S288c) gives CAI ~0.87 and GC ~36 % for a poorly adapted CDS; same range here
    assert a['caiBefore'] < 0.65 and 0.80 <= a['caiAfter'] <= 0.95
    assert 30 <= a['gcAfter'] <= 45
    assert a['caiAfter'] == round(cai(a['sequence']), 3)


def test_codon_optimization_leaves_an_already_adapted_sequence_alone():
    # an optimized sequence (CAI ~0.88, no sites, no long runs) is kept as entered, like VectorBuilder returns a yeast-adapted
    # CDS unchanged: so optimizing twice changes nothing
    once = optimize_cds(_long_cargo())['sequence']
    again = optimize_cds(once)
    assert again['status'] == 'kept' and again['sequence'] == once and again['changed'] == 0
    assert 'Already well adapted' in again['reason']


def test_codon_optimization_skips_a_sequence_that_is_not_a_codon_multiple():
    result = optimize_cds('ATGAAATT')
    assert result['status'] == 'skipped' and not result['optimized'] and result['sequence'] == 'ATGAAATT'
    assert 'multiple of 3' in result['reason']


def test_codon_optimization_keeps_an_internal_stop_codon_as_entered():
    cds = 'ATG' + 'GCTGCTGCT' * 4 + 'TAG' + 'GCTGCTGCT' * 4
    result = optimize_cds(cds)
    assert translate(result['sequence']) == translate(cds)
    assert result['sequence'][39:42] == 'TAG'


def test_no_site_can_appear_across_the_seam_to_the_adapter():
    # every user sequence is optimized against the real flanks of the slot it ends up in: Level 0 adapter, and the
    # neighbour in the Level 1 module (overhang + GC spacer); in the cargo module the part sits as reverse complement
    for module in ('cargo', 'nc'):
        for slot in (1, 2, 3, 4, 5):
            for seed in range(8):
                rng = random.Random(seed)
                cds = 'ATG' + ''.join(rng.choice(['GAA', 'GAC', 'GGT', 'CTC', 'GAG', 'ACC', 'GTC', 'TTC', 'AAG']) for _ in range(60))
                result = codon_optimize_part(cds, module, slot)
                assert translate(result['sequence']) == translate(cds)
                assert result['forbiddenAfter'] == [], (module, slot, seed)


def test_every_user_sequence_in_a_full_design_is_site_free_from_level0_to_the_level1_modules():
    def seq(i):
        return 'ATG' + ('GAAGACGGTCTCGAGACCGTCTTC' + 'AAGGAAGACGGTCTC') * i

    design = _design(
        cargoSeq=_long_cargo()[:90] + 'GGTCTCGAAGACGAGACCGTCTTC' + _long_cargo()[90:],
        cargo_slots={'1': {'kind': 'custom', 'label': 'PartA', 'seq': seq(2)}, '2': {'kind': 'linker', 'id': 'GSSS2'},
                     '4': {'kind': 'linker', 'id': 'GSSS2'}, '5': {'kind': 'custom', 'label': 'PartB', 'seq': seq(3)}},
        nc_slots={'1': {'kind': 'custom', 'label': 'PartC', 'seq': seq(2)}, '2': {'kind': 'linker', 'id': 'GSSS2'},
                  '4': {'kind': 'linker', 'id': 'GSSS2'}, '5': {'kind': 'custom', 'label': 'PartD', 'seq': seq(1)}},
    )
    users = [c for c in design['level0Constructs'] if c['isUser']]
    assert [c['label'] for c in users] == ['PartA', 'GFP', 'PartB', 'PartC', 'PartD']
    report = {r['label']: r for r in design['codonOptimization']}
    assert set(report) == {'PartA', 'GFP', 'PartB', 'PartC', 'PartD'}
    assert all(r['status'] == 'optimized' and r['sitesRemoved'] and r['sitesLeft'] == [] for r in report.values())
    for c in users:
        assert c['codon']['status'] == 'optimized'
        a, b = location_span(c['insert']['location'])
        assert find_forbidden(c['sequence'][a - 1 - 5:b + 5]) == []          # insert + its seams in the BbsI-cut fragment
        assert 'Codon-optimized for S. cerevisiae' in c['genbank']
    assert all(c['codon'] is None for c in design['level0Constructs'] if not c['isUser'])
    # the assembled Level 1 modules (BsaI) carry no BsaI/BbsI site anywhere
    cargo, _, nc = design['level1Constructs']
    assert find_forbidden(cargo['sequence']) == [] and find_forbidden(nc['sequence']) == []
    # the cargo shown in the design is the optimized one, with the same protein as entered
    assert find_forbidden(design['cargo']['sequence']) == []


def test_library_parts_and_library_cargo_are_never_codon_optimized():
    preset = next(e for e in load_parts()['level0_inserts'] if e['category'] == 'cargo' and len(e['sequence']) % 3 == 0
                  and e['sequence'][-3:] not in ('TAA', 'TAG', 'TGA'))
    design = _design(cargoSeq=preset['sequence'], cargoLabel=preset['part'])
    assert design['codonOptimization'] == []
    assert design['cargo']['sequence'] == preset['sequence']
    gene = next(c for c in design['level0Constructs'] if c['module'] == 'cargo_site' and c['slot'] == 3)
    assert not gene['isUser'] and gene['codon'] is None


def test_validate_previews_the_codon_optimization():
    out = json.loads(_run_cli('validate', {'cargoSeq': SITE_CDS}).stdout)
    codon = out['validation']['codonOptimization']
    assert codon['status'] == 'optimized' and codon['sitesRemoved'] and codon['sitesLeft'] == []
    assert 'codonOptimization' not in json.loads(_run_cli('validate', {'cargoSeq': 'ATGTAA'}).stdout)['validation']      # invalid sequence: no preview


# Amino acid sequences as input: translated into DNA with the yeast codon table

PROTEIN = 'MSKGEELFTGVVPILVELDGDVNGHKFSVSGEGEGDATYGKLTLKFICTTGKLPVPWPTLVTTFGYGVQCFARYPDHMKQHDFFKSAMPEGYVQERTIFFKDDGNYK'


def test_dna_and_protein_input_are_told_apart():
    assert not is_protein('ATGAAATTTGGTCTCGAAGAC') and not is_protein('atg aaa ttt\n ggt ctc') and not is_protein('AUGAAAUUUGGUCUC')
    assert is_protein(PROTEIN) and is_protein('>sp|P42212 GFP\nMSKGEELFTGVV') and is_protein('MKV*')
    assert not is_protein('') and not is_protein('>header only')


def test_validate_cargo_accepts_a_protein_and_counts_the_dna_it_becomes():
    v = validate_cargo(PROTEIN)
    assert v['ok'] and v['isProtein'] and v['aa'] == len(PROTEIN) and v['length'] == 3 * len(PROTEIN) and v['clean'] == PROTEIN
    assert validate_cargo('>name\n' + PROTEIN[:60] + ' 1\n' + PROTEIN[60:])['clean'] == PROTEIN        # header, spaces, digits dropped
    assert validate_cargo(PROTEIN + '*')['ok'] and validate_cargo(PROTEIN + '*')['clean'] == PROTEIN and 'removes the stop codon' in validate_cargo(PROTEIN + '*')['warnings'][0]
    assert validate_cargo('MKV*LL' * 6)['warnings'][0].startswith('Stop (*) at residue 4')
    assert validate_cargo('MKVLLAGHE')['ok'] is False and 'too short' in validate_cargo('MKVLLAGHE')['errors'][0]
    assert validate_cargo('MKVLLAGHE', kind='part')['ok']                                            # no minimum for own parts
    assert validate_cargo('MKVXLLAGHEEDL', kind='part')['invalidChars'] == 1


def test_a_protein_is_back_translated_with_yeast_codons_and_no_sites():
    result = optimize_cds(PROTEIN, protein=True)
    assert result['fromProtein'] and result['status'] == 'optimized' and result['caiBefore'] is None
    assert translate(result['sequence']) == PROTEIN and len(result['sequence']) == 3 * len(PROTEIN)
    assert 0.8 <= result['caiAfter'] <= 0.95 and 30 <= result['gcAfter'] <= 45
    assert result == optimize_cds(PROTEIN, protein=True)                                                  # reproducible
    # a repetitive protein with several site-like codon motifs stays site-free and keeps its protein
    hard = 'MEDGLETVF' * 8 + 'KKKKKKKKKKKK'
    out = optimize_cds(hard, protein=True)
    assert translate(out['sequence']) == hard and find_forbidden(out['sequence']) == []


def test_design_builds_from_protein_input_everywhere():
    design = _design(
        cargoSeq=PROTEIN,
        cargo_slots={'1': {'kind': 'custom', 'label': 'PartA', 'seq': 'MKVLLAGHEEDLGSGS'}, '2': {'kind': 'linker', 'id': 'GSSS2'}},
        nc_slots={'5': {'kind': 'custom', 'label': 'PartB', 'seq': 'MAAAKKEEDDGSGSGS'}, '4': {'kind': 'linker', 'id': 'GSSS2'}},
    )
    users = {c['label']: c for c in design['level0Constructs'] if c['isUser']}
    assert set(users) == {'PartA', 'GFP', 'PartB'}
    assert translate(design['cargo']['sequence']) == PROTEIN and design['cargo']['bp'] == 3 * len(PROTEIN)
    assert translate(users['GFP']['insert']['sequence']) == PROTEIN                       # cargo site is shown in reading direction
    for label, protein in (('PartA', 'MKVLLAGHEEDLGSGS'), ('PartB', 'MAAAKKEEDDGSGSGS')):
        seq = users[label]['insert']['sequence']
        assert translate(seq) == protein + '*'                                              # both are the last part of their ORF: stop added
    report = {r['label']: r for r in design['codonOptimization']}
    assert all(r['fromProtein'] and r['status'] == 'optimized' for r in report.values()) and len(report) == 3
    assert 'Back-translated' in users['PartB']['genbank']
    cargo, _, nc = design['level1Constructs']
    assert find_forbidden(cargo['sequence']) == [] and find_forbidden(nc['sequence']) == []


def test_custom_shell_can_be_a_protein_too():
    shell = 'MSNQ' * 40
    design = _design(nanocompartment='custom', customNanocompartment={'label': 'Mine', 'seq': shell}, cargo_slots={})
    assert design['nanocompartment']['custom'] and translate(design['nanocompartment']['sequence']) == shell
    assert design['nanocompartment']['shellBp'] == 3 * len(shell)


def test_validate_previews_a_protein_back_translation():
    out = json.loads(_run_cli('validate', {'cargoSeq': PROTEIN}).stdout)['validation']
    assert out['isProtein'] and out['codonOptimization']['fromProtein']


def test_to_dna_gives_the_screening_a_dna_form_of_every_input():
    out = json.loads(_run_cli('to_dna', {'sequences': ['atg aaa\nttt 12', 'MKV*', '>name\nMK']}).stdout)
    assert out['ok'] and out['dna'] == ['ATGAAATTT', 'ATGAAAGTTTAA', 'ATGAAA']


# ---------------------------------------------------------------------------------------------------------
# Start and stop codon are added by the software per slot (parts are stored bare)

def _insert_of(design, module, slot):
    return next(c for c in design['level0Constructs'] if c['module'] == module and c['slot'] == slot)['insert']['sequence']


def test_start_codon_goes_on_the_first_coding_part_of_each_orf_and_stop_behind_the_last():
    from Biologik.level0_design.parts_db import find_inserts
    marker = find_inserts('marker', 'spycatcher')[0]['sequence']
    spytag = find_inserts('marker', 'spytag')[0]['sequence']
    shell = find_inserts('shell', 'E-Tm')[0]['sequence']
    # NC module reads Type 0.1 -> 0.5, cargo module Type 0.5 -> 0.1; the cargo is a user sequence that already has its ATG
    design = _design(cargoSeq=_long_cargo(),
                     nc_slots={'1': {'kind': 'marker', 'id': 'spycatcher'}, '2': {'kind': 'linker', 'id': 'GSSS2'},
                               '4': {'kind': 'linker', 'id': 'GSSS2'}, '5': {'kind': 'marker', 'id': 'spytag'}},
                     cargo_slots={'1': {'kind': 'tp'}, '2': {'kind': 'linker', 'id': 'GSSS2'}})
    assert _insert_of(design, 'nc_site', 1) == 'ATG' + marker                      # first: start codon, no stop
    assert _insert_of(design, 'nc_site', 3) == shell                               # in the middle: bare, nothing added
    assert _insert_of(design, 'nc_site', 5) == spytag + 'TAA'                      # last: stop codon, no start
    tp = find_inserts('tp', 'TP-Tm', 'cargo_site', 1)[0]['sequence']
    assert _insert_of(design, 'cargo_site', 1) == tp + 'TAA'                       # Type 0.1 of the cargo module is its C terminus


def test_the_central_part_gets_start_and_stop_when_only_ncs_spacers_follow():
    from Biologik.level0_design.parts_db import find_inserts
    shell = find_inserts('shell', 'E-Tm')[0]['sequence']
    design = _design(cargo_slots={'1': {'kind': 'ncs'}})
    assert _insert_of(design, 'nc_site', 3) == 'ATG' + shell + 'TAA'                  # nothing coding behind it: the shell ends the ORF
    # with a linker behind the shell, the stop moves behind the linker and the shell stays without one
    linker = find_inserts('linker', 'GSSS2', 'nc_site', 4)[0]['sequence']
    with_linker = _design(cargo_slots={'1': {'kind': 'ncs'}}, nc_slots={'4': {'kind': 'linker', 'id': 'GSSS2'}})
    assert _insert_of(with_linker, 'nc_site', 3) == 'ATG' + shell
    assert _insert_of(with_linker, 'nc_site', 4) == linker + 'TAA'
    # NCS spacers never get start or stop codons: they are the one NCS sequence
    assert {c['insert']['sequence'] for c in design['level0Constructs'] if c['label'] == 'NCS'} == {'CCGTCAGGGCGCGTCAGCGGGTGTTGGCGGGTGTCGGGG'}


def test_a_library_cargo_with_its_own_atg_and_stop_is_not_doubled():
    from Biologik.level0_design.data import get_libraries
    yegfp = next(c for c in get_libraries()['cargoPresets'] if c['id'] == 'yegfp')['seq']
    assert not yegfp.startswith('ATG') or yegfp[3:6] == 'ATG'                       # stored bare
    for entered in (yegfp, 'ATG' + yegfp, 'ATG' + yegfp + 'TAA'):
        design = _design(cargoSeq=entered, cargoLabel='yeGFP', cargo_slots={'1': {'kind': 'ncs'}})
        gene = next(c for c in design['level0Constructs'] if c['module'] == 'cargo_site' and c['slot'] == 3)
        assert gene['isUser'] is False and gene['insert']['sequence'] == 'ATG' + yegfp + 'TAA'


def test_an_own_sequence_keeps_its_atg_and_gets_no_second_one():
    design = _design(cargoSeq=_long_cargo(), nc_slots={'1': {'kind': 'custom', 'label': 'Mine', 'seq': 'ATG' + 'GCT' * 20},
                                                      '2': {'kind': 'linker', 'id': 'GSSS2'}})
    mine = _insert_of(design, 'nc_site', 1)
    assert translate(mine) == 'M' + 'A' * 20 and not mine.startswith('ATGATG')
    bare = _design(cargoSeq=_long_cargo(), nc_slots={'1': {'kind': 'custom', 'label': 'Mine', 'seq': 'GCT' * 20},
                                                    '2': {'kind': 'linker', 'id': 'GSSS2'}})
    assert translate(_insert_of(bare, 'nc_site', 1)) == 'M' + 'A' * 20            # no ATG entered: the builder adds it


def test_the_vault_is_a_nanocompartment_without_a_targeting_peptide():
    design = _design(nanocompartment='mvp', cargo_slots={'1': {'kind': 'ncs'}})
    assert design['nanocompartment']['id'] == 'mvp' and design['targetingPeptide'] is None
    shell = next(c for c in design['level0Constructs'] if c['module'] == 'nc_site' and c['slot'] == 3)
    assert shell['what'] == 'nanocompartment shell (toolkit part)' and shell['insert']['sequence'].startswith('ATG')
    with pytest.raises(ValueError, match='no targeting peptide'):
        _design(nanocompartment='mvp', cargo_slots={'1': {'kind': 'tp'}, '2': {'kind': 'linker', 'id': 'GSSS2'}})


def test_parts_and_constructs_tell_whether_their_plasmid_is_built():
    from Biologik.level0_design.data import get_libraries
    libs = get_libraries()
    linker = next(l for l in libs['linkers'] if l['id'] == 'GSSS2')
    assert linker['status']['nc']['2'] == 'stock' and linker['status']['nc']['4'] == 'not_built'   # 0.4 L2 on NC is only listed in the table
    assert next(c for c in libs['cargoPresets'] if c['id'] == 'nlucp')['status'] == 'no_stock'
    assert next(c for c in libs['cargoPresets'] if c['id'] == 'yegfp')['status'] == 'stock'
    assert libs['ncsStatus']['nc']['1'] == {'plain': 'stock'}
    design = _design(cargoSeq=_long_cargo(), nc_slots={'4': {'kind': 'linker', 'id': 'GSSS2'}})
    status = {(c['module'], c['slot']): c['plasmidStatus'] for c in design['level0Constructs']}
    assert status[('nc_site', 4)] == 'not_built' and status[('nc_site', 3)] == 'stock'
    assert status[('cargo_site', 3)] is None                                              # your own cargo has no plasmid


def test_level0_primers_carry_the_structure_check_of_the_finished_primers():
    pytest.importorskip('primer3')
    design = _design(cargoSeq=_long_cargo())
    own = next(c for c in design['level0Constructs'] if c['isUser'] and c['primers']['possible'])
    st = own['primers']['structure']
    for key in ('hairpin', 'selfDimer'):
        assert set(st[key]) == {'forward', 'reverse'} and all(isinstance(v['ok'], bool) for v in st[key].values())
    assert isinstance(st['heteroDimer']['deltaG'], float)


# Combined NCS spacers: one Level 0 part that replaces two neighbouring NCS parts (Types 0.1 + 0.2 and 0.4 + 0.5)

NCS_BASE = {'nanocompartment': 'tmari', 'cargoSeq': 'ATGGCTAAAGGTGAAGAACTGTTCACCGGTGTTGTTCCAATCTTGGTTGAATTGGATGGTGATGTTAACGGTCACAAATTCTCT', 'cargoLabel': 'X'}


def _levels_with_ncs(nc_slots=None, cargo_slots=None):
    from Biologik.level0_design.design import design_construct
    return design_construct({**NCS_BASE, 'ncSlots': nc_slots or {}, 'cargoSlots': cargo_slots or {}})


def test_the_combined_ncs_adapters_join_the_left_of_one_type_and_the_right_of_the_next():
    adapters = {a['id']: a for a in load_parts()['type_overhangs']}
    for combined, left, right in (('0.12', '0.1', '0.2'), ('0.12rc', '0.1rc', '0.2'), ('0.45', '0.4', '0.5'), ('0.45rc', '0.4', '0.5rc')):
        a = adapters[combined]
        roles = {o['role']: o['sequence_top_strand'] for o in a['overhangs']}
        left_roles = {o['role']: o['sequence_top_strand'] for o in adapters[left]['overhangs']}
        right_roles = {o['role']: o['sequence_top_strand'] for o in adapters[right]['overhangs']}
        assert roles['level1_N'] == left_roles['level1_N'] and roles['level1_C'] == right_roles['level1_C']
        assert roles['level0_N'] == left_roles['level0_N'] and roles['level0_C'] == right_roles['level0_C']
        assert a['type_slot'] is None and a['covers_slots'] in ([1, 2], [4, 5])
        assert a['length_bp'] == len(a['sequence']) == 42
        # the overhang between the two parts (the level 1 C of the left, the level 1 N of the right) is gone
        assert left_roles['level1_C'] not in [o['sequence_top_strand'] for o in a['overhangs']]


def test_a_combined_ncs_is_one_part_and_sets_both_of_its_slots():
    from Biologik.level0_design.slots import module_units, resolve_slots
    slots = resolve_slots({'1': {'kind': 'ncs12'}, '4': {'kind': 'ncs'}, '5': {'kind': 'ncs45'}}, 'nc')
    assert [slots[n]['kind'] for n in (1, 2, 4, 5)] == ['ncs12', 'ncs12', 'ncs45', 'ncs45']          # the other slot follows automatically
    assert module_units(slots) == [(12, [1, 2]), (3, [3]), (45, [4, 5])]
    with pytest.raises(ValueError, match='only fits'):
        resolve_slots({'4': {'kind': 'ncs12'}}, 'nc')
    with pytest.raises(ValueError, match='remove the other part'):
        resolve_slots({'1': {'kind': 'ncs12'}, '2': {'kind': 'linker', 'id': 'GSSS2'}}, 'nc')


def test_a_combined_ncs_builds_one_level0_part_and_a_shorter_module():
    separate = _levels_with_ncs()
    combined = _levels_with_ncs({'1': {'kind': 'ncs12'}, '4': {'kind': 'ncs45'}}, {'2': {'kind': 'ncs12'}, '5': {'kind': 'ncs45'}})
    for module in ('ncModule', 'cargoModule'):
        assert [p['type'] for p in combined['level0'][module]] == ['Type 0.12', 'Type 0.3', 'Type 0.45']
        assert [p['slots'] for p in combined['level0'][module]] == [[1, 2], [3], [4, 5]]
    keys = {(c['module'], c['slot']): c for c in combined['level0Constructs']}
    assert sorted(slot for (module, slot) in keys if module == 'nc_site') == [3, 12, 45]
    assert {c['adapter'] for c in combined['level0Constructs'] if c['slot'] in (12, 45)} == {'0.12', '0.12rc', '0.45', '0.45rc'}
    for slot in (12, 45):
        ncs = keys[('nc_site', slot)]
        assert ncs['insert']['sequence'] == 'CCGTCAGGGCGCGTCAGCGGGTGTTGGCGGGTGTCGGGG' and ncs['label'] == 'NCS'
        assert ncs['genbank'].startswith('LOCUS       ' + f'Level0.{slot}_NCS_NC') and ncs['type'] == f'Type 0.{slot}'
    # one NCS (39 bp) + its 4 nt overhang + 2 nt frame spacer less per pair
    sep_len = {m['site']: m['length'] for m in separate['level1Constructs']}
    com_len = {m['site']: m['length'] for m in combined['level1Constructs']}
    for site in ('nc_site', 'cargo_site'):
        assert sep_len[site] - com_len[site] == 2 * (39 + 4 + 2)
    assert combined['level2Construct'] is not None


def test_the_combined_ncs_keeps_the_stop_codon_logic():
    design = _levels_with_ncs({'1': {'kind': 'ncs12'}, '4': {'kind': 'linker', 'id': 'GSSS2'}, '5': {'kind': 'ncs'}})
    assert [p['stop'] for p in design['level0']['ncModule']] == [False, False, True, False]        # 0.12, shell, linker (ends the ORF), NCS
    flags = {(c['module'], c['slot']): c['stopCodon'] for c in design['level0Constructs']}
    assert flags[('nc_site', 4)] is True and flags[('nc_site', 12)] is False

def test_registry_links_point_to_registry_igem_org_and_the_linked_parts_exist_there():
    from Biologik.level0_design.parts_db import inserts
    urls = {e['registry_url'] for e in inserts() if e['registry_url']}
    assert urls and all(u.startswith('https://registry.igem.org/parts/bba-') for u in urls)
    linked = {(e['category'], e['part']) for e in inserts() if e['registry_url']}
    # every plasmid of a linked part carries the link, and parts that are not in the Registry yet carry none
    assert all(e['registry_url'] for e in inserts() if (e['category'], e['part']) in linked)
    assert not any(e['registry_url'] for e in inserts() if (e['category'], e['part']) in {('linker', 'GSSS2'), ('linker', 'GSSS4'), ('tp', 'TP-Tm')})


# What the guide tells about the Level 2 insert: the overhangs, no BbsI or BsaI site, no terminators or vector parts

LEVEL2_SLOT_VARIANTS = [
    {},
    {'ncSlots': {'1': {'kind': 'ncs12'}, '4': {'kind': 'ncs45'}}, 'cargoSlots': {'2': {'kind': 'ncs12'}}},
    {'ncSlots': {'1': {'kind': 'marker', 'id': 'spycatcher'}, '2': {'kind': 'linker', 'id': 'GSSS3'},
                 '4': {'kind': 'linker', 'id': 'GGS2'}, '5': {'kind': 'marker', 'id': 'spytag'}},
     'cargoSlots': {'1': {'kind': 'ncs'}, '2': {'kind': 'linker', 'id': 'GSSS2'}, '4': {'kind': 'linker', 'id': 'GSSS4'}, '5': {'kind': 'intein', 'id': 'int'}}},
]


@pytest.mark.parametrize('nanocompartment', ['tmari', 'mxan', 'qther', 'mvp'])
@pytest.mark.parametrize('variant', range(len(LEVEL2_SLOT_VARIANTS)))
def test_the_level2_insert_has_the_two_level2_overhangs_and_no_bbsi_or_bsai_site(nanocompartment, variant):
    from Biologik.level0_design.design import design_construct
    design = design_construct({'nanocompartment': nanocompartment, 'cargoSeq': _long_cargo(), 'cargoLabel': 'X', **LEVEL2_SLOT_VARIANTS[variant]})
    insert = design['level2Construct']['sequence']
    assert insert[:4] == 'CCAA' and insert[-4:] == 'AATG'
    for site in ('GAAGAC', 'GTCTTC', 'GGTCTC', 'GAGACC'):
        assert site not in insert, f'{site} in the Level 2 insert'
    assert design['level2Construct']['junctions']['n'] == 'CCAA' and design['level2Construct']['junctions']['c'] == 'AATG'


def test_the_terminators_marker_and_origins_come_from_the_level2_vector_not_from_the_insert():
    """The insert is only the two modules and the promoter; the vector pESC-HIS carries the terminators right next to the overhangs."""
    backbone = next(iter(load_parts()['level2_backbones']))
    seq = backbone['sequence']

    def span(location):
        numbers = [int(n) for n in re.findall(r'\d+', location)]
        return min(numbers), max(numbers)

    features = {f['qualifiers'].get('label', [''])[0]: f for f in backbone['features']}
    adh1_end = span(features['ADH1 terminator']['location'])[1]
    cyc1_start = span(features['CYC1 terminator']['location'])[0]
    left_a, _ = span(backbone['receiver_overhangs']['5_prime']['location'])
    _, right_b = span(backbone['receiver_overhangs']['3_prime']['location'])
    assert adh1_end + 1 == left_a and right_b + 1 == cyc1_start                      # terminators sit right at the overhangs
    insert_sequences = [m['sequence'] for m in _real_design()['level1Constructs']]
    adh1 = seq[span(features['ADH1 terminator']['location'])[0] - 1:adh1_end]
    cyc1 = seq[cyc1_start - 1:span(features['CYC1 terminator']['location'])[1]]
    level2 = _real_design()['level2Construct']['sequence']
    assert adh1 not in level2 and cyc1 not in level2 and insert_sequences
    assert 'HIS3' in features and 'AmpR' in features and any('2μ' in k or '2μ' in k for k in features)   # marker and origins stay in the vector
