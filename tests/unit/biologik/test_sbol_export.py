"""The SBOL 3 export of the Builder (frontend/sbol.js), read back with the reference library pySBOL3.

The browser converts the GenBank text of the engine, so the test does the same: the engine writes the GenBank text, Node converts it
with the real frontend/sbol.js, pySBOL3 loads and validates the result."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from Biologik.level0_design.design import build_genbank, design_construct

sbol3 = pytest.importorskip("sbol3")
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is needed to run frontend/sbol.js")

ROOT = Path(__file__).resolve().parents[3]
CONVERT = """
import vm from 'node:vm'
import { readFileSync } from 'node:fs'
const ctx = {}; ctx.window = ctx; vm.createContext(ctx)
vm.runInContext(readFileSync(process.argv[2], 'utf8'), ctx)
process.stdout.write(ctx.ENCORE_SBOL.fromGenbank(readFileSync(0, 'utf8')))
"""


def to_sbol(genbank: str, tmp_path: Path) -> sbol3.Document:
    script = tmp_path / "convert.mjs"
    script.write_text(CONVERT)
    done = subprocess.run(["node", str(script), str(ROOT / "frontend" / "sbol.js")], input=genbank, capture_output=True, text=True, check=True)
    path = tmp_path / "out.ttl"
    path.write_text(done.stdout)
    doc = sbol3.Document()
    doc.read(str(path))
    return doc


def feature_count(genbank: str) -> int:
    return len(re.findall(r"^ {5}\S+\s+\S", genbank.split("ORIGIN")[0].split("FEATURES")[1], re.M))


@pytest.fixture(scope="module")
def design():
    return design_construct({**json.loads((ROOT / "docs" / "examples" / "oxygen-free-space-request.json").read_text()), "genbank": True})


def test_the_level_2_plasmid_is_valid_sbol_with_every_feature_and_the_same_sequence(design, tmp_path):
    genbank = design["level2Construct"]["plasmid"]["genbank"]
    doc = to_sbol(genbank, tmp_path)
    assert not list(doc.validate())
    (component,) = [o for o in doc.objects if isinstance(o, sbol3.Component)]
    assert len(component.features) == feature_count(genbank)
    sequence = component.sequences[0].lookup().elements
    assert sequence.upper() == design["level2Construct"]["plasmid"]["sequence"]
    assert "https://identifiers.org/SO:0000988" in component.types      # circular


def test_the_complete_genbank_of_all_levels_gives_one_component_per_record(design, tmp_path):
    genbank = build_genbank(design)
    doc = to_sbol(genbank, tmp_path)
    assert not list(doc.validate())
    assert len([o for o in doc.objects if isinstance(o, sbol3.Component)]) == genbank.count("\nLOCUS") + genbank.startswith("LOCUS")


def test_a_feature_on_the_reverse_strand_keeps_its_orientation(design, tmp_path):
    genbank = design["level2Construct"]["plasmid"]["genbank"]
    doc = to_sbol(genbank, tmp_path)
    (component,) = [o for o in doc.objects if isinstance(o, sbol3.Component)]
    reverse = [f for f in component.features if f.locations[0].orientation.endswith("SO:0001031")]
    assert len(reverse) == len(re.findall(r"^ {5}\S+\s+\S*complement\(", genbank, re.M))
