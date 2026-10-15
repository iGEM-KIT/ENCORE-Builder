"""Integrity of the encapsulin database (encapsulin_selector/data/) and of the generated selector-data.js.

The data is curated by hand (and exported from the master Excel), so these checks catch the typical slips: an assembly
that points to a candidate that does not exist, an ID with a space, a duplicated ID, or a selector-data.js that was
forgotten after a data change.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "encapsulin_selector" / "data"


def load_dir(name):
    return {p.stem: json.loads(p.read_text(encoding="utf8")) for p in sorted((DATA / name).glob("*.json")) if not p.name.startswith("_")}


@pytest.fixture(scope="module")
def candidates():
    return load_dir("candidates")


@pytest.fixture(scope="module")
def assemblies():
    return load_dir("assemblies")


@pytest.fixture(scope="module")
def sequences():
    return load_dir("sequences")


@pytest.fixture(scope="module")
def pores():
    return load_dir("pores")


def test_every_data_file_is_valid_json_and_the_folders_are_not_empty():
    for folder in ("candidates", "assemblies", "sequences", "pores", "evidence"):
        files = [p for p in (DATA / folder).glob("*.json") if not p.name.startswith("_")]
        assert files, f"{folder} is empty"
        for path in files:
            json.loads(path.read_text(encoding="utf8"))
    for name in ("citation_links.json", "doi_index.json", "meta.json", "vocabularies.json"):
        json.loads((DATA / name).read_text(encoding="utf8"))


def test_candidate_ids_match_their_file_names_and_have_no_padding_or_duplicates(candidates):
    ids = [c["candidate_id"] for c in candidates.values()]
    assert len(set(ids)) == len(ids)
    for stem, entry in candidates.items():
        assert entry["candidate_id"] == stem, f"{stem}.json carries the ID {entry['candidate_id']!r}"
        assert entry["candidate_id"] == entry["candidate_id"].strip() and " " not in entry["candidate_id"]


def test_assemblies_point_to_existing_candidates_and_have_unique_ids(candidates, assemblies):
    for stem, entry in assemblies.items():
        assert entry["assembly_id"] == stem
        assert entry["candidate_id"] in candidates, f"{stem}: unknown candidate {entry['candidate_id']}"
    assert len({a["assembly_id"] for a in assemblies.values()}) == len(assemblies)


def test_the_reference_assembly_of_a_candidate_exists_and_belongs_to_it(candidates, assemblies):
    for candidate in candidates.values():
        ref = candidate.get("reference_assembly_id")
        if ref:
            assert ref in assemblies, f"{candidate['candidate_id']}: reference assembly {ref} does not exist"
            assert assemblies[ref]["candidate_id"] == candidate["candidate_id"]


def test_sequences_and_pores_point_to_existing_records(candidates, assemblies, sequences, pores):
    for stem, entry in sequences.items():
        assert entry["candidate_id"] in candidates, f"sequence {stem}: unknown candidate"
    for stem, entry in pores.items():
        assert entry["candidate_id"] in candidates, f"pore {stem}: unknown candidate"
        assert entry["assembly_id"] in assemblies, f"pore {stem}: unknown assembly {entry['assembly_id']}"
        assert assemblies[entry["assembly_id"]]["candidate_id"] == entry["candidate_id"]


def test_assembly_numbers_are_plausible(assemblies):
    for stem, a in assemblies.items():
        t = a.get("T_number")
        assert t is None or (isinstance(t, (int, float)) and t > 0), f"{stem}: T_number {t!r}"
        n = a.get("shell_subunit_count")
        assert n is None or (isinstance(n, int) and n > 0), f"{stem}: shell_subunit_count {n!r}"
        d = a.get("shell_diameter_nm")
        if isinstance(d, (int, float)):
            assert 5 <= d <= 200, f"{stem}: shell diameter {d} nm"


def test_citation_links_point_to_known_dois():
    dois = {entry["doi"].lower() for entry in json.loads((DATA / "doi_index.json").read_text(encoding="utf8"))}
    links = json.loads((DATA / "citation_links.json").read_text(encoding="utf8"))
    unknown = sorted({link["doi"] for link in links if link["doi"] and link["doi"].lower() not in dois})
    assert unknown == [], f"citation links with a DOI that is not in doi_index.json: {unknown[:5]}"


def test_generated_selector_data_is_up_to_date():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    generated = ROOT / "encapsulin_selector" / "selector-data.js"
    before = generated.read_bytes()
    try:
        result = subprocess.run([node, str(ROOT / "scripts" / "build-selector-data.mjs")], capture_output=True, text=True, cwd=ROOT)
        assert result.returncode == 0, result.stderr
        after = generated.read_bytes()
    finally:
        generated.write_bytes(before)                                                # the test never leaves a changed file behind
    assert after == before, "encapsulin_selector/selector-data.js is stale: run `pnpm build:selector-data` and commit it"


def test_the_generated_selector_data_has_the_counts_of_the_data_folders(candidates, assemblies, sequences, pores):
    text = (ROOT / "encapsulin_selector" / "selector-data.js").read_text(encoding="utf8")
    assert "ENCAPSULIN_SELECTOR_DATA" in text
    for ident in list(candidates)[:5] + list(assemblies)[:5]:
        assert ident in text


# The parts database (Biologik/level0_design/parts/): the file-level rules that the builder relies on

PARTS = ROOT / "Biologik" / "level0_design" / "parts"


def part_files():
    return [p for p in PARTS.rglob("*.json") if not p.name.startswith("_")]


def test_every_parts_file_is_valid_json_with_an_id_that_matches_the_file_name():
    assert part_files()
    for path in part_files():
        entry = json.loads(path.read_text(encoding="utf8"))
        assert entry.get("id"), path
        assert entry["id"] == path.stem or path.parent.name == "level0_inserts", f"{path.name}: id {entry['id']!r}"


IUPAC = r"[ACGTRYKMSWBDHVNacgtrykmswbdhvn]+"


def test_part_sequences_are_plain_dna_and_their_length_field_is_right():
    """Inserts, promoters and adapters must be plain A/C/G/T; only the imported backbones and terminators may carry IUPAC codes."""
    for path in part_files():
        entry = json.loads(path.read_text(encoding="utf8"))
        seq = entry.get("sequence")
        if not seq:
            continue
        imported = path.parent.name in ("level0_backbones", "level1_backbones", "level2_backbones", "terminators")
        assert re.fullmatch(IUPAC if imported else r"[ACGTacgt]+", seq), f"{path.name}: not plain DNA"
        if entry.get("length_bp") is not None:
            assert entry["length_bp"] == len(seq), f"{path.name}: length_bp {entry['length_bp']} but {len(seq)} bases"


def test_the_only_ambiguous_base_in_the_imported_sequences_is_the_known_one():
    """The Level 2 backbone pESC-HIS (and the ADH1 terminator cut from it) has one Y (C or T) at position 2083 in the source
    GenBank file. It is pinned here so that a second one cannot slip in unnoticed; if the source file is corrected, remove it."""
    found = {}
    for path in part_files():
        seq = json.loads(path.read_text(encoding="utf8")).get("sequence") or ""
        positions = [i + 1 for i, base in enumerate(seq.upper()) if base not in "ACGT"]
        if positions:
            found[path.name] = positions
    assert found == {"pESC-HIS-lvl2-dest.json": [2083], "adh1-terminator.json": [123]}


def test_registry_links_are_complete_urls_to_the_igem_registry():
    for path in (PARTS / "level0_inserts").glob("*.json"):
        if path.name.startswith("_"):
            continue
        entry = json.loads(path.read_text(encoding="utf8"))
        for plasmid in entry["plasmids"]:
            url = plasmid.get("registry_url")
            assert url is None or re.fullmatch(r"https://registry\.igem\.org/parts/bba-[0-9a-z]+", url), f"{path.name}: {url}"
