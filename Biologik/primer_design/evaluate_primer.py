try:
    import primer3
except ImportError as exc:
    raise ImportError(
        "The primer3 Python package is required. Install it with `pip install primer3-py`."
    ) from exc

# cal/mol; hairpin threshold is stricter than dimer thresholds because hairpins
# form intramolecularly and persist at higher effective concentrations
HETERO_THRESHOLD = -9000
HOMODIMER_THRESHOLD = -9000
HAIRPIN_THRESHOLD = -3000

# structures melting below this temperature are unlikely to interfere with PCR
TM_THRESHOLD = 45.0


def evaluate_primer(primer_fw: str, primer_rv: str) -> dict:
    fw = primer_fw.upper()
    rv = primer_rv.upper()

    hd = primer3.bindings.calc_heterodimer(fw, rv)
    sd_fw = primer3.bindings.calc_homodimer(fw)
    sd_rv = primer3.bindings.calc_homodimer(rv)
    hp_fw = primer3.bindings.calc_hairpin(fw)
    hp_rv = primer3.bindings.calc_hairpin(rv)

    issues = []

    hetero_dg = hd.dg
    hetero_ok = hetero_dg >= HETERO_THRESHOLD or hd.tm < TM_THRESHOLD
    if not hetero_ok:
        issues.append(
            f"Heterodimer: ΔG = {hetero_dg} cal/mol "
            f"(threshold: {HETERO_THRESHOLD} cal/mol) – too stable"
        )

    self_fw_dg = sd_fw.dg
    self_fw_ok = self_fw_dg >= HOMODIMER_THRESHOLD or sd_fw.tm < TM_THRESHOLD
    if not self_fw_ok:
        issues.append(
            f"Homodimer (forward): ΔG = {self_fw_dg} cal/mol "
            f"(threshold: {HOMODIMER_THRESHOLD} cal/mol) – too stable"
        )

    self_rv_dg = sd_rv.dg
    self_rv_ok = self_rv_dg >= HOMODIMER_THRESHOLD or sd_rv.tm < TM_THRESHOLD
    if not self_rv_ok:
        issues.append(
            f"Homodimer (reverse): ΔG = {self_rv_dg} cal/mol "
            f"(threshold: {HOMODIMER_THRESHOLD} cal/mol) – too stable"
        )

    hairpin_fw_dg = hp_fw.dg
    hairpin_fw_ok = hairpin_fw_dg >= HAIRPIN_THRESHOLD or hp_fw.tm < TM_THRESHOLD
    if not hairpin_fw_ok:
        issues.append(
            f"Hairpin (forward): ΔG = {hairpin_fw_dg} cal/mol "
            f"(threshold: {HAIRPIN_THRESHOLD} cal/mol) – too stable"
        )

    hairpin_rv_dg = hp_rv.dg
    hairpin_rv_ok = hairpin_rv_dg >= HAIRPIN_THRESHOLD or hp_rv.tm < TM_THRESHOLD
    if not hairpin_rv_ok:
        issues.append(
            f"Hairpin (reverse): ΔG = {hairpin_rv_dg} cal/mol "
            f"(threshold: {HAIRPIN_THRESHOLD} cal/mol) – too stable"
        )

    all_ok = len(issues) == 0

    return {
        "valid": all_ok,
        "hetero_dimer_dG": hetero_dg,
        "self_fw_dG": self_fw_dg,
        "self_rv_dG": self_rv_dg,
        "hairpin_fw_dG": hairpin_fw_dg,
        "hairpin_rv_dG": hairpin_rv_dg,
        "hetero_ok": hetero_ok,
        "self_fw_ok": self_fw_ok,
        "self_rv_ok": self_rv_ok,
        "hairpin_fw_ok": hairpin_fw_ok,
        "hairpin_rv_ok": hairpin_rv_ok,
        "issues": issues,
        "recommendation": (
            "Primer pair is suitable"
            if all_ok
            else "Primer pair should be optimized (see issues)"
        ),
    }
