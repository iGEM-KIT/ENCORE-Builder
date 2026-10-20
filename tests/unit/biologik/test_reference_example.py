"""The worked example of the README ("Reproduce the example") must keep giving the same result."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from Biologik.level0_design.design import design_construct

ROOT = Path(__file__).resolve().parents[3]
REQUEST = ROOT / "docs" / "examples" / "oxygen-free-space-request.json"

CARGO_PARTS = [("SpyTag", "Type 0.1"), ("3×(GSSS)", "Type 0.2"), ("LGB4", "Type 0.3"), ("NCS", "Type 0.4"), ("NCS", "Type 0.5")]
NC_PARTS = [("SpyCatcher", "Type 0.1"), ("3×(GSSS)", "Type 0.2"), ("E-Qt", "Type 0.3"), ("NCS", "Type 0.4"), ("NCS", "Type 0.5")]


def _sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def test_the_readme_example_gives_the_documented_construct():
    design = design_construct(json.loads(REQUEST.read_text()))

    assert [(p["label"], p["type"]) for p in design["level2Construct"]["parts"]] == (
        CARGO_PARTS + [("GAL1-10", "Promoter")] + NC_PARTS
    )
    assert [c["name"] for c in design["level1Constructs"]] == ["Level1_Cargo", "Level1_Promoter", "Level1_NC"]
    assert design["level2Construct"]["junctions"] == {"n": "CCAA", "cargoPromoter": "CGTT", "promoterNc": "TGAT", "c": "AATG"}
    assert design["level2Construct"]["length"] == 2555
    assert len(design["level2Construct"]["plasmid"]["sequence"]) == 8274
    assert [p["full"] for p in design["primers"]] == [
        "GGTCTCNCCAAGAAGGCTTTCTTTATGGCCGCCG",
        "GGTCTCNGCAAGGTGCTTTCACGGAAAAGCAAGAGG",
    ]


def test_the_example_is_identical_on_every_run():
    request = json.loads(REQUEST.read_text())
    first, second = design_construct(request), design_construct(request)
    assert _sha(first["level2Construct"]["sequence"]) == _sha(second["level2Construct"]["sequence"])
    assert _sha(first["level2Construct"]["plasmid"]["sequence"]) == _sha(second["level2Construct"]["plasmid"]["sequence"])


def test_the_command_line_gives_the_same_construct():
    done = subprocess.run(
        [sys.executable, "-m", "Biologik.level0_design.cli", "design"],
        input=REQUEST.read_text(), capture_output=True, text=True, cwd=ROOT, check=True,
    )
    answer = json.loads(done.stdout)
    assert answer["ok"] is True
    assert answer["design"]["level2Construct"]["length"] == 2555
