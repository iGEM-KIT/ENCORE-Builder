import json
import random
import re
import subprocess
import sys

import pytest

from Biologik.level0_design.codon import cai, find_forbidden, optimize_cds, translate
from Biologik.level0_design.design import (attach_adapter, build_genbank, codon_optimize_part, design_construct,
                                           make_primer_pair)
from Biologik.level0_design.genbank_writer import location_span
from Biologik.level0_design.parts_db import load_parts
from Biologik.level0_design.sequence import is_protein, reverse_complement, validate_cargo


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
        'cargoPresets', 'inteins', 'level0Backbones', 'level1Backbones', 'level2Backbones', 'linkers',
        'nanocompartments', 'ncs', 'promoters', 'surfaceMarkers', 'targetingPeptides',
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


def test_stop_codon_is_only_set_where_the_user_put_an_ncs_with_stop():
    # Kein automatisches Stopcodon: ohne ausdruecklich gewaehlten "NCS mit Stopcodon" traegt kein Slot eines.
    for slots in (CARGO_SLOTS_C_TERM, CARGO_SLOTS_N_TERM):
        module = _design(cargo_slots=slots)['level0']['cargoModule']
        assert not any(p['stop'] for p in module)

    # Mit ausdruecklich gewaehltem NCS mit Stopcodon (NC Site, direkt hinter der Shell) sitzt es genau dort.
    nc_module = _design(nc_slots={'4': {'kind': 'ncsstop'}})['level0']['ncModule']
    assert [p['stop'] for p in nc_module] == [False, False, False, True, False]


def test_surface_marker_sits_at_the_chosen_terminus():
    # Ein Marker (oder jede andere CDS) in Type 0.1/0.5 braucht zwingend einen Linker
    # im Nachbarslot (0.2/0.4) — anders als frueher gibt es keinen automatischen L1-Linker
    # mehr, die Wahl liegt beim Nutzer.
    n_term = _design(nc_slots={'1': {'kind': 'marker', 'id': 'spycatcher'}, '2': {'kind': 'linker', 'id': 'GSSS2'}})['level0']['ncModule']
    c_term = _design(nc_slots={'4': {'kind': 'linker', 'id': 'GSSS2'}, '5': {'kind': 'marker', 'id': 'spycatcher'}})['level0']['ncModule']

    assert n_term[0]['kind'] == 'mark' and n_term[1]['role'] == 'nc-linker'
    assert c_term[4]['kind'] == 'mark' and c_term[3]['role'] == 'nc-linker'
    assert not any(p['stop'] for p in n_term + c_term)


def test_without_a_marker_the_slots_stay_inert_spacers():
    nc_module = _design()['level0']['ncModule']

    assert [p['role'] for p in nc_module] == ['ncs', 'ncs', 'shell', 'ncs', 'ncs']
    assert [p['stop'] for p in nc_module] == [False] * 5


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
    assert translate(constructs['Part B']['insert']['sequence']) == translate('ATG' + 'CCC' * 10)   # codon-optimized, same protein
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
    assert translate(insert) == translate(cds)            # Cargo Site wird in Leserichtung gezeigt (codon-optimiert, gleiches Protein)
    fwd, rev = pr['forward'], pr['reverse']
    assert fwd['sequence'] == pr['clamp'] + flank5 + fwd['anneal']
    assert insert.startswith(fwd['anneal'])
    assert rev['sequence'] == pr['clamp'] + reverse_complement(flank3) + rev['anneal']
    assert insert.endswith(reverse_complement(rev['anneal']))
    # PCR-Produkt = Konstrukt + je ein Polster
    assert pr['productLength'] == construct['length'] + 2 * len(pr['clamp'])
    # BbsI-Erkennungsstelle liegt hinter dem Polster, damit das Enzym am Produktende schneidet
    assert fwd['sequence'][len(pr['clamp']):].startswith('GAAGAC')
    assert rev['sequence'][len(pr['clamp']):].startswith('GAAGAC')
    assert pr['internalSites'] == [] or all('site' in s for s in pr['internalSites'])
    assert '/label="%s"' % fwd['name'] in construct['genbank']
    assert '/label="%s"' % rev['name'] in construct['genbank']
    assert 'primer_bind' in construct['genbank']


def test_level0_primers_need_a_real_long_enough_insert(monkeypatch):
    import Biologik.level0_design.design as design_module
    monkeypatch.setattr(design_module, 'find_inserts', lambda *args, **kwargs: [])          # no inserts -> placeholders
    design = _design(cargoSeq=_long_cargo())
    placeholder = next(c for c in design['level0Constructs'] if not c['isReal'])
    assert placeholder['primers']['possible'] is False
    assert 'real sequence' in placeholder['primers']['reason']

    monkeypatch.undo()
    short = next(c for c in _design()['level0Constructs'] if c['module'] == 'cargo_site' and c['slot'] == 3)
    assert short['primers']['possible'] is False and 'below 150 bp' in short['primers']['reason']


def test_level0_primers_flag_internal_restriction_sites(monkeypatch):
    import Biologik.level0_design.design as design_module
    cds = _long_cargo()
    cds = cds[:60] + 'GAAGAC' + cds[66:]                 # BbsI-Stelle mitten im Insert
    monkeypatch.setattr(design_module, 'codon_optimize_part',
                        lambda sequence, module, slot, protein=False: optimize_cds(sequence) | {'sequence': sequence, 'optimized': False})
    design = _design(cargoSeq=cds)                       # ohne Optimierung bleibt die Stelle, und die Primer warnen davor
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
    # liegt auch im Gesamt-GenBank-Export
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
# Level 1 (BsaI) und Level 2 (BbsI): die Assemblies werden hier wirklich "verdaut" nachgerechnet.

def _bsai_fragment(plasmid: str) -> str:
    """Top-Strand-Fragment, das BsaI aus einem Level-0-Plasmid schneidet (Stuecke zwischen den beiden Schnitten)."""
    left = plasmid.index('GGTCTC')                    # Top-Strand-Stelle, schneidet 1 nt dahinter, Overhang = 4 nt
    right = plasmid.index('GAGACC')                   # Stelle auf dem Gegenstrang, schneidet 1 nt davor
    return plasmid[left + 7:right - 1]


def _bbsi_piece(plasmid: dict) -> str:
    """Top-Strand-Stueck zwischen den beiden BbsI-Schnitten des Level-1-Plasmids: 2 nt hinter GAAGAC bzw. 2 nt vor
    GTCTTC, jeweils mit 4-nt-Overhang. Die beiden Stellen sind die des Backbones links/rechts des Inserts."""
    seq = plasmid['sequence']
    left = 2                                                # GAAGAC an 3..8
    right = plasmid['insertEnd'] - 2                        # GTCTTC beginnt am G von TTGT
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

    # Die fuenf Fragmente, die BsaI aus den echten Level-0-Plasmiden schneidet, ergeben genau das Modul.
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
    # Das Cargo-Modul liegt als Reverse Complement auf dem Top-Strand (antisense).
    assert gene['strand'] == 'antisense'
    assert cargo['sequence'][gene['start'] - 1:gene['end']] == reverse_complement(design['cargo']['sequence'])
    mine = next(p for p in nc['parts'] if p['label'] == 'MyPart')
    assert mine['strand'] == 'sense' and translate(nc['sequence'][mine['start'] - 1:mine['end']]) == translate('ATG' + 'GCT' * 20)
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
    # BbsI schneidet aus dem Plasmid genau das Stueck zwischen den Level-2-Overhangs
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
    assert pl['sequence'].startswith(backbone['sequence'][:2127] + 'CCAA')
    assert pl['sequence'][pl['insertEnd'] - 4:pl['insertEnd']] == 'AATG' and pl['sequence'][pl['insertEnd']:pl['insertEnd'] + 20] == backbone['sequence'][2951:2971]
    for label in ('HIS3', 'AmpR', 'ADH1 terminator', 'CYC1 terminator', 'GFP', 'BbLvl2N', 'BbLvl2C'):
        assert f'/label="{label}"' in pl['genbank']
    assert 'BbsI Rec Site' not in pl['genbank']                       # the cassette's own BbsI sites are gone


def test_internal_restriction_sites_are_reported_on_level1(monkeypatch):
    import Biologik.level0_design.design as design_module
    cds = _long_cargo()
    cds = cds[:60] + 'GGTCTC' + cds[66:]
    monkeypatch.setattr(design_module, 'codon_optimize_part',
                        lambda sequence, module, slot, protein=False: optimize_cds(sequence) | {'sequence': sequence, 'optimized': False})
    cargo = _design(cargoSeq=cds)['level1Constructs'][0]     # ohne Optimierung bleibt die Stelle
    assert any('BsaI' in s and 'GFP' in s for s in cargo['internalSites'])


def test_libraries_ship_level1_and_level2_backbones_with_a_ready_genbank_text():
    from Biologik.level0_design.data import get_libraries
    libs = get_libraries()
    for key, name, bp, labels in (('level1Backbones', 'pAGM1311', 2621, ('KanR', 'ori', 'lacZ-alpha', 'BbsI rec site', 'BsaI rec site')),
                                  ('level2Backbones', 'pESC', 6544, ('HIS3', 'AmpR', 'ADH1 terminator', 'CYC1 terminator'))):
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
    # NC-Modul und Promotor bleiben unveraendert; Plasmid und Level 2 arbeiten mit der Top-Strand-Orientierung weiter
    assert promoter['shown'] is None and nc['shown'] is None
    assert cargo['plasmid']['sequence'][cargo['plasmid']['insertStart'] - 1:cargo['plasmid']['insertEnd']] == cargo['sequence']
    assert shown['genbank'] in build_genbank(design)


# ---------------------------------------------------------------------------------------------------------
# Leseraster: 2-nt-Frame-Spacer direkt vor dem Insert jedes Adapters (parts/type_overhangs/)

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

    # cargo ORF (antisense module, read in the rotated view): cargo -> B -> A, no stop, multiple of 3
    shown = cargo_module['shown']
    ps = {p['label']: p for p in shown['parts']}
    orf = shown['sequence'][ps['G']['start'] - 1:ps['A']['end']]
    assert len(orf) == len(parts['cargo']) + len(parts['B']) + len(parts['A']) + 12 and len(orf) % 3 == 0
    assert not {'TAA', 'TAG', 'TGA'} & set(_orf_codons(orf))

    cargo_orf = orf
    # NC ORF: C -> D
    ps = {p['label']: p for p in nc_module['parts']}
    nc_orf = nc_module['sequence'][ps['C']['start'] - 1:ps['D']['end']]
    assert len(nc_orf) == len(parts['C']) + len(parts['D']) + 6 and len(nc_orf) % 3 == 0
    assert not {'TAA', 'TAG', 'TGA'} & set(_orf_codons(nc_orf))

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
        assert '/label="Frame spacer"' in construct['genbank']
        assert '/label="Frame spacer"' in construct['plasmid']['genbank']
    for module in design['level1Constructs']:
        if module['site'] != 'promoter':
            assert module['genbank'].count('/label="Frame spacer"') == 5
            assert module['plasmid']['genbank'].count('/label="Frame spacer"') == 5
    assert design['level1Constructs'][0]['shown']['genbank'].count('/label="Frame spacer"') == 5
    assert design['level2Construct']['plasmid']['genbank'].count('/label="Frame spacer"') == 10


# ---------------------------------------------------------------------------------------------------------
# Bestellung: Oligos fuer zu kurze Teile, Lagerstatus der Toolkit-Teile

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
    assert tiny['insert']['sequence'] in fragment and translate(tiny['insert']['sequence']) == translate(short)

    # real parts long enough for primers, and placeholders, get no oligos
    gene = next(c for c in design['level0Constructs'] if c['label'] == 'GFP')
    assert gene['oligos'] is None and gene['primers']['possible']
    assert all(c['oligos'] is None for c in design['level0Constructs'] if not c['isReal'])


def test_constructs_carry_the_stock_flag_of_toolkit_parts():
    design = _design(cargoSeq=_long_cargo(), cargo_slots={'4': {'kind': 'linker', 'id': 'GSSS3'}, '5': {'kind': 'tp'}},
                     nc_slots={'4': {'kind': 'custom', 'label': 'Mine', 'seq': 'ATG' + 'GCT' * 20}})
    flags = {(c['module'], c['slot']): c['onStock'] for c in design['level0Constructs']}
    assert flags[('nc_site', 3)] is True                                           # toolkit shell E-Tm (glycerol stock: yes)
    assert flags[('cargo_site', 4)] is False                                       # 0.4 L3rc: glycerol stock "nein"
    assert flags[('cargo_site', 5)] is True                                        # TP, N-terminal, Type 0.5
    assert flags[('nc_site', 4)] is None and flags[('cargo_site', 3)] is None      # own sequences have no stock status


# ---------------------------------------------------------------------------------------------------------
# Level-0-Inserts-Datenbank (parts/level0_inserts/): reine Teilsequenzen aus den Level-0-Plasmiden

def test_insert_database_is_consistent():
    from Biologik.level0_design.parts_db import inserts
    entries = inserts()
    assert len(entries) == 37
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
            assert e['site'] == 'nc_site' and e['type_slot'] == 3 and e['sequence'].startswith('ATG')
        if e['category'] == 'cargo':
            assert e['site'] == 'cargo_site' and e['type_slot'] == 3 and e['sequence'].startswith('ATG')
    # coding parts must be a multiple of 3 for the fusions to stay in frame — one known exception in the supplied plasmids
    coding = [e for e in entries if e['category'] in ('shell', 'cargo', 'linker', 'tp', 'marker', 'intein')]
    assert [e['id'] for e in coding if len(e['sequence']) % 3] == ['Lvl0.5_a_026']


def test_libraries_offer_each_part_only_where_a_level0_plasmid_exists():
    from Biologik.level0_design.data import get_libraries
    libs = get_libraries()
    linkers = {l['id']: l['slots'] for l in libs['linkers']}
    assert linkers == {'GGS2': {'nc': [], 'cargo': [2, 4]}, 'GSSS2': {'nc': [2], 'cargo': [2]},
                       'GSSS3': {'nc': [2], 'cargo': [2, 4]}, 'GSSS4': {'nc': [2], 'cargo': []}}
    assert {m['id']: m['slots'] for m in libs['surfaceMarkers']} == {'spycatcher': {'nc': [1], 'cargo': []}, 'spytag': {'nc': [], 'cargo': [1]}}
    assert libs['inteins'][0]['slots'] == {'nc': [], 'cargo': [1]}
    assert all(t['slots'] == {'nc': [], 'cargo': [1, 5]} for t in libs['targetingPeptides'])
    # NCS: the stop variant sits behind the central part (NC: Type 0.4, cargo: Type 0.2), plain NCS elsewhere
    assert libs['ncs'] == {'nc': {'1': ['plain'], '2': ['plain'], '4': ['stop'], '5': ['plain']},
                           'cargo': {'1': ['plain'], '2': ['stop'], '4': ['plain'], '5': ['plain']}}
    assert [c['id'] for c in libs['cargoPresets']] == ['yegfp', 'lgb4', 'nlucp', 'civcpo', 'mvp', 'pabp', 'pabp-rrm1-4', 'pabp-rrm1-2']
    assert [n['shellBp'] for n in libs['nanocompartments']] == [798, 864, 849]


def test_a_cargo_taken_unchanged_from_the_library_is_a_toolkit_part_with_a_stock_flag():
    from Biologik.level0_design.data import get_libraries
    yegfp = next(c for c in get_libraries()['cargoPresets'] if c['id'] == 'yegfp')
    design = _design(cargoSeq=yegfp['seq'], cargoLabel='yeGFP')
    cargo = next(c for c in design['level0Constructs'] if c['module'] == 'cargo_site' and c['slot'] == 3)
    assert cargo['isUser'] is False and cargo['onStock'] is True and cargo['what'] == 'cargo (toolkit part)'
    edited = _design(cargoSeq=yegfp['seq'][:-3] + 'GCT', cargoLabel='yeGFP')
    mine = next(c for c in edited['level0Constructs'] if c['module'] == 'cargo_site' and c['slot'] == 3)
    assert mine['isUser'] is True and mine['onStock'] is None


def test_toolkit_parts_use_the_inserts_of_their_own_site_and_slot():
    design = _design(cargoSeq=_long_cargo(), cargo_slots={'1': {'kind': 'ncs'}, '2': {'kind': 'ncsstop'}, '4': {'kind': 'linker', 'id': 'GSSS3'}, '5': {'kind': 'tp'}},
                     nc_slots={'1': {'kind': 'marker', 'id': 'spycatcher'}, '2': {'kind': 'linker', 'id': 'GSSS2'}, '4': {'kind': 'ncsstop'}})
    by = {(c['module'], c['slot']): c for c in design['level0Constructs']}
    # the cargo module sits antisense: its linker is the reverse complement of the sense insert in the DB
    from Biologik.level0_design.parts_db import find_inserts
    gsss3 = find_inserts('linker', 'GSSS3', 'cargo_site', 4)[0]['sequence']
    assert by[('cargo_site', 4)]['insert']['sequence'] == gsss3                       # shown rotated -> sense again
    assert by[('nc_site', 1)]['insert']['sequence'] == find_inserts('marker', 'spycatcher')[0]['sequence']
    assert by[('nc_site', 4)]['insert']['sequence'] == find_inserts('ncs', 'ncs', 'nc_site', 4, ncs_role='stop')[0]['sequence']
    assert by[('cargo_site', 5)]['insert']['sequence'] == find_inserts('tp', 'TP-Tm', 'cargo_site', 5, variant='n_term')[0]['sequence']


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
        # oligo pair: every part with a real sequence below 150 bp — own or toolbox, no matter which
        assert (c['oligos'] is not None) == (c['isReal'] and n < 150)
    mid = next(c for c in design['level0Constructs'] if c['label'] == 'Mid')            # 93 bp own part -> oligos, no primers
    assert mid['oligos']['possible'] is True and mid['primers']['possible'] is False and 'below 150 bp' in mid['primers']['reason']
    toolkit = next(c for c in design['level0Constructs'] if not c['isUser'] and len(c['insert']['sequence']) >= 150)
    assert 'only designed for your own sequences' in toolkit['primers']['reason'] and toolkit['oligos'] is None   # the shell
    ncs = [c for c in design['level0Constructs'] if c['label'] == 'NCS']
    assert ncs and all(c['oligos'] and c['oligos']['possible'] for c in ncs)



def test_ncs_spacers_with_a_stop_codon_are_flagged_on_their_construct():
    design = _design(cargoSeq=_long_cargo(), nc_slots={'4': {'kind': 'ncsstop'}})
    flags = {(c['module'], c['slot']): c['stopCodon'] for c in design['level0Constructs']}
    assert flags[('nc_site', 4)] is True and flags[('nc_site', 5)] is False and flags[('nc_site', 3)] is False
    stop = next(c for c in design['level0Constructs'] if c['module'] == 'nc_site' and c['slot'] == 4)
    assert stop['what'] == 'NCS spacer with stop codon (toolkit part)'


def test_the_stop_codon_of_an_ncs_with_stop_is_marked_in_construct_oligos_and_plasmid():
    design = _design(cargoSeq=_long_cargo(), cargo_slots={'1': {'kind': 'ncs'}, '2': {'kind': 'ncsstop'}},
                     nc_slots={'4': {'kind': 'ncsstop'}})
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
    design = _design(cargoSeq=_long_cargo(), nc_slots={'4': {'kind': 'ncsstop'}})
    for c in design['level0Constructs']:
        if not c['oligos']:
            continue
        gb, o = c['oligos']['genbank'], c['oligos']
        assert gb.startswith('LOCUS       ' + f"Level0.{c['slot']}_Oligos_") and gb.strip().endswith('//')
        assert gb.count('primer_bind') == 2 and f"/label=\"{o['top']['name']}\"" in gb and f"/label=\"{o['bottom']['name']}\"" in gb
        assert f"{o['annealedLength']} bp" in gb.splitlines()[0]
    stop = next(c for c in design['level0Constructs'] if c['module'] == 'nc_site' and c['slot'] == 4)
    assert '/label="Stop codon"' in stop['oligos']['genbank'] and '/label="Frame spacer"' in stop['oligos']['genbank']


def test_toolbox_constructs_name_the_level0_plasmid_they_come_from():
    design = _design(cargoSeq=_long_cargo())
    shell = next(c for c in design['level0Constructs'] if c['module'] == 'nc_site' and c['slot'] == 3)
    assert shell['plasmid_source'] == {'id': 'Lvl0.3_a_016', 'name': '0.3E-Tm'}
    own = next(c for c in design['level0Constructs'] if c['isUser'])
    assert own['plasmid_source'] is None


# Codon-Optimierung fuer S. cerevisiae: jede eingegebene Sequenz, Protein unveraendert, keine BsaI/BbsI-Stellen

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
    # CDS unchanged — so optimizing twice changes nothing
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


def test_validate_previews_the_codon_optimization_and_checks_the_optimized_mrna():
    out = json.loads(_run_cli('validate', {'cargoSeq': SITE_CDS}).stdout)
    codon = out['validation']['codonOptimization']
    assert codon['status'] == 'optimized' and codon['sitesRemoved'] and codon['sitesLeft'] == []
    assert 'codonOptimization' not in json.loads(_run_cli('validate', {'cargoSeq': 'ATGTAA'}).stdout)['validation']      # invalid sequence: no preview


# Aminosaeuresequenzen als Eingabe: werden mit der Hefe-Codon-Tabelle in DNA uebersetzt

PROTEIN = 'MSKGEELFTGVVPILVELDGDVNGHKFSVSGEGEGDATYGKLTLKFICTTGKLPVPWPTLVTTFGYGVQCFARYPDHMKQHDFFKSAMPEGYVQERTIFFKDDGNYK'


def test_dna_and_protein_input_are_told_apart():
    assert not is_protein('ATGAAATTTGGTCTCGAAGAC') and not is_protein('atg aaa ttt\n ggt ctc') and not is_protein('AUGAAAUUUGGUCUC')
    assert is_protein(PROTEIN) and is_protein('>sp|P42212 GFP\nMSKGEELFTGVV') and is_protein('MKV*')
    assert not is_protein('') and not is_protein('>header only')


def test_validate_cargo_accepts_a_protein_and_counts_the_dna_it_becomes():
    v = validate_cargo(PROTEIN)
    assert v['ok'] and v['isProtein'] and v['aa'] == len(PROTEIN) and v['length'] == 3 * len(PROTEIN) and v['clean'] == PROTEIN
    assert validate_cargo('>name\n' + PROTEIN[:60] + ' 1\n' + PROTEIN[60:])['clean'] == PROTEIN        # header, spaces, digits dropped
    assert validate_cargo(PROTEIN + '*')['ok'] is False and 'Stop codon' in validate_cargo(PROTEIN + '*')['errors'][0]
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
        assert translate(seq) == protein
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
    assert out['isProtein'] and out['codonOptimization']['fromProtein'] and out['mrnaStructure'] is not None
