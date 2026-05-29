try:
    import primer3
except ImportError as exc:
    raise ImportError(
        "The primer3 Python package is required. Install it with `pip install primer3-py`."
    ) from exc

# Grenzwerte in cal/mol
HETERO_THRESHOLD = -9000     # Heterodimere -9 kcal/mol
HOMODIMER_THRESHOLD = -9000   # Homodimere-9 kcal/mol
HAIRPIN_THRESHOLD = -3000     # Hairpins wichtiger und daher strenger bewertet (-3 kcal/mol)

TM_THRESHOLD = 45.0           # Strukturen, die unter 45°C schmelzen, sind meist unkritisch


def evaluate_primer(primer_fw: str, primer_rv: str):
    # Beurteilt ein Primerpaar auf Sekundärstrukturen (Heterodimer, Homodimer, Hairpin)
    # gibt eine detaillierte Bewertung mit Empfehlung zurück

    fw = primer_fw.upper()
    rv = primer_rv.upper()

    # Berechnung der thermodynamischen Werte
    hd = primer3.bindings.calc_heterodimer(fw, rv)
    sd_fw = primer3.bindings.calc_homodimer(fw)
    sd_rv = primer3.bindings.calc_homodimer(rv)
    hp_fw = primer3.bindings.calc_hairpin(fw)
    hp_rv = primer3.bindings.calc_hairpin(rv)

    # Detaillierte Bewertung
    issues = []

    # Heterodimer Check (dG und Tm)
    hetero_dg = hd.dg
    hetero_ok = hetero_dg >= HETERO_THRESHOLD or hd.tm < TM_THRESHOLD
    if not hetero_ok:
        issues.append(
            f"Heterodimer: ΔG = {hetero_dg} cal/mol "
            f"(Grenzwert: {HETERO_THRESHOLD} cal/mol) – zu stabil"
        )

    # Homodimer Forward
    self_fw_dg = sd_fw.dg
    self_fw_ok = self_fw_dg >= HOMODIMER_THRESHOLD or sd_fw.tm < TM_THRESHOLD
    if not self_fw_ok:
        issues.append(
            f"Self-Homodimer Forward: ΔG = {self_fw_dg} cal/mol "
            f"(Grenzwert: {HOMODIMER_THRESHOLD} cal/mol) – zu stabil"
        )

    # Homodimer Reverse
    self_rv_dg = sd_rv.dg
    self_rv_ok = self_rv_dg >= HOMODIMER_THRESHOLD or sd_rv.tm < TM_THRESHOLD
    if not self_rv_ok:
        issues.append(
            f"Self-Homodimer Reverse: ΔG = {self_rv_dg} cal/mol "
            f"(Grenzwert: {HOMODIMER_THRESHOLD} cal/mol) – zu stabil"
        )

    # Hairpin Forward
    hairpin_fw_dg = hp_fw.dg
    hairpin_fw_ok = hairpin_fw_dg >= HAIRPIN_THRESHOLD or hp_fw.tm < TM_THRESHOLD
    if not hairpin_fw_ok:
        issues.append(
            f"Hairpin Forward: ΔG = {hairpin_fw_dg} cal/mol "
            f"(Grenzwert: {HAIRPIN_THRESHOLD} cal/mol) – zu stabil"
        )

    # Hairpin Reverse
    hairpin_rv_dg = hp_rv.dg
    hairpin_rv_ok = hairpin_rv_dg >= HAIRPIN_THRESHOLD or hp_rv.tm < TM_THRESHOLD
    if not hairpin_rv_ok:
        issues.append(
            f"Hairpin Reverse: ΔG = {hairpin_rv_dg} cal/mol "
            f"(Grenzwert: {HAIRPIN_THRESHOLD} cal/mol) – zu stabil"
        )

    all_ok = len(issues) == 0

    # Rückgabe als vollständig strukturiertes Dict
    return {
        "valid": all_ok,
        "primer_fw": primer_fw,
        "primer_rv": primer_rv,
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
            "Primerpaar ist geeignet"
            if all_ok
            else "Primerpaar sollte optimiert werden (siehe issues)"
        ),
    }
