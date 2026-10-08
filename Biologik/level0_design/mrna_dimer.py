"""mRNA self structure (optional, needs ViennaRNA): not only for the cargo
but for EVERY sequence entered by the user (cargo, own shell,
own module), see cli.py cmd_validate().

Two separate phenomena that can both block a scanning ribosome and
prevent translation:

  - selfFold:  a single mRNA folds back onto itself
               (hairpin / secondary structure WITHIN one copy).
  - selfDimer: two copies of the same mRNA anneal to each other
               (intermolecular duplex BETWEEN two copies).

Both need ViennaRNA (``pip install ViennaRNA``: see
Biologik/requirements.txt). If it is missing that is no error: the check is
simply left out, just like primer3 elsewhere falls back to the
Wallace estimate: design_construct() still returns a result.

A raw minimum free energy (MFE) alone cannot be compared fairly between sequences:
every RNA has a certain baseline folding energy simply from its length and GC content. So the MFE of the real sequence is
compared against the background of several randomly shuffled variants (same base composition)
of the same sequence: a z-score, how many standard deviations more strongly the real sequence
folds/dimerizes than would be expected for a random sequence of the same composition.
A clearly negative z-score = more structured/self-complementary than chance.
The shuffling is a simple base shuffle (not dinucleotide preserving): a deliberate simplification.

This is a thermodynamic MFE estimate, NOT a binding probability in the kinetic/concentration sense
(that would need intracellular concentrations and kinetics data, which this tool does not have).
"""

from __future__ import annotations


import random

# ViennaRNA calls get roughly quadratically slower with the sequence length. Measured (RNA.fold + RNA.duplexfold together, one sequence):
# 500bp ~0.3s · 1000bp ~1.4s · 1500bp ~3.2s · 2000bp ~5.7s · 3000bp ~13.8s
# TARGET_SECONDS is the time budget PER check (self-fold or self-dimer,
# each including the random background); the live check runs in the background
# after a typing pause, not on every keystroke, so a few seconds of
# waiting for a long sequence are fine here.
TARGET_SECONDS = 10.0
# rough calibration factor from the measurements above (seconds per bp^2), with a
# safety margin upwards so the budget is not blown
TIME_PER_BP2 = 1.6e-6
MIN_SHUFFLES = 2  # fewer than 2 gives no meaningful standard deviation
MAX_SHUFFLES = 10  # more hardly adds any precision for short sequences
MAX_LEN = 3000  # longer: check skipped entirely (even folding once would be too slow)
SHUFFLE_SEED = 20260928  # deterministic: same sequence -> same result


def _estimated_seconds(length: int) -> float:
    return TIME_PER_BP2 * length * length


def _shuffle_count(length: int, target_seconds: float = TARGET_SECONDS) -> int:
    """How many random background sequences still fit in the time budget?

        0 means: even 2 shuffles would blow the budget; then there is only
        the raw MFE without z-score/risk level. Shorter sequences get more
        shuffles (better statistics), longer ones fewer, but rarely fewer than 2.

    """
    est = _estimated_seconds(length)
    if est <= 0:
        return MAX_SHUFFLES
    n = int(target_seconds / est) - 1
    if n < MIN_SHUFFLES:
        return 0
    return min(MAX_SHUFFLES, n)


def _shuffled(seq: str, rng: random.Random) -> str:
    chars = list(seq)
    rng.shuffle(chars)
    return "".join(chars)


def _zscore(observed: float, background: list) -> float | None:
    n = len(background)
    if n < 2:
        return None
    mean = sum(background) / n
    variance = sum((x - mean) ** 2 for x in background) / n
    sd = variance ** 0.5
    if sd == 0:
        return None
    return (observed - mean) / sd


def _risk_from_z(z: float | None) -> str | None:
    if z is None:
        return None
    if z <= -3:
        return "high"
    if z <= -2:
        return "moderate"
    return "low"


def _one_check(seq_rna: str, mfe_fn, rng: random.Random, shuffles: int) -> dict:
    observed = mfe_fn(seq_rna)
    result = {"deltaG": round(observed, 1), "zScore": None, "risk": None, "shuffles": 0}
    if shuffles > 0:
        background = [mfe_fn(_shuffled(seq_rna, rng)) for _ in range(shuffles)]
        z = _zscore(observed, background)
        result["zScore"] = round(z, 2) if z is not None else None
        result["risk"] = _risk_from_z(z)
        result["shuffles"] = shuffles
    return result


def check_mrna_structure(sense_seq: str, target_seconds: float = TARGET_SECONDS) -> dict:
    """``sense_seq``: a validated, fusion-ready CDS in sense/coding direction
        (cargo, own shell or own module); this is also exactly the
        mRNA sequence (with U instead of T)."""
    seq = (sense_seq or "").upper()
    if len(seq) < 8:
        return {"available": False, "reason": "Sequence too short to fold."}
    if len(seq) > MAX_LEN:
        return {
            "available": False,
            "reason": f"Sequence longer than {MAX_LEN} bp: mRNA structure check skipped for performance.",
        }

    try:
        import RNA
    except ImportError:
        return {
            "available": False,
            "reason": (
                "ViennaRNA is not installed: mRNA self-fold/self-dimer check skipped. "
                "Install it with `pip install ViennaRNA` (see Biologik/requirements.txt)."
            ),
        }

    rna = seq.replace("T", "U")
    rng = random.Random(SHUFFLE_SEED)
    shuffles = _shuffle_count(len(rna), target_seconds)

    def fold_mfe(s: str) -> float:
        return RNA.fold(s)[1]

    def duplex_mfe(s: str) -> float:
        return RNA.duplexfold(s, s).energy

    self_fold = _one_check(rna, fold_mfe, rng, shuffles)
    self_dimer = _one_check(rna, duplex_mfe, rng, shuffles)

    return {
        "available": True,
        "length": len(seq),
        "selfFold": self_fold,
        "selfDimer": self_dimer,
    }


STOP_CODONS = ("TAA", "TAG", "TGA")
MODULE_TARGET_SECONDS = 5.0  # per check; a design has two modules, each with a self-fold and a self-dimer check


def module_mrna(view: dict) -> dict:
    """The mRNA that is translated from an assembled Level 1 module, and its self-fold / self-dimer check.

        ``view`` is the module in its reading direction (the NC module as it is, the cargo module in its rotated view): `sequence` and
        `parts` (each with `start`, `end` (1-based, insert only), `label`, `what`). The mRNA runs from the first coding part (NCS
        spacers in front of it are left out) to the first stop codon in the reading frame, including that stop codon, and
        with the junctions (overhang + frame spacer, 6 nt) between the parts. An NCS with stop codon contributes only
        up to its stop codon, an NCS behind the last coding part without a stop codon is not included. Without any stop
        codon the mRNA ends with the last coding part. 5' and 3' UTR of the promoter / terminator are not part of it."""
    seq = (view.get("sequence") or "").upper()
    parts = sorted(view.get("parts") or [], key=lambda p: p["start"])
    coding = [p for p in parts if "NCS" not in p.get("what", "")]
    if not coding:
        return {"available": False, "reason": "The module has no coding part."}
    start = coding[0]["start"] - 1
    # where a stop codon may be looked for: up to the end of the last coding part or of an NCS with stop codon behind it
    limit = max([coding[-1]["end"]] + [p["end"] for p in parts if "stop codon" in p.get("what", "") and p["start"] > coding[-1]["end"]])
    end = coding[-1]["end"]
    ends_with_stop = False
    for i in range(start, limit - 2, 3):
        if seq[i:i + 3] in STOP_CODONS:
            end, ends_with_stop = i + 3, True
            break
    mrna = seq[start:end]
    labels = [p["label"] for p in parts if p["start"] - 1 < end and p["end"] > start]
    check = check_mrna_structure(mrna, MODULE_TARGET_SECONDS)
    return {**check, "length": len(mrna), "endsWithStop": ends_with_stop, "parts": labels, "sequence": mrna}
