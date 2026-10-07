"""mRNA-Selbststruktur (optional, braucht ViennaRNA): nicht nur fuer die Cargo,
sondern fuer JEDE vom Nutzer selbst eingegebene Sequenz (Cargo, eigene Shell,
eigenes Modul), siehe cli.py cmd_validate().

Zwei getrennte Phänomene, die beide ein scannendes Ribosom blockieren und die
Translation verhindern können:

  - selfFold:  eine einzelne mRNA faltet sich auf sich selbst zurück
               (Haarnadelstruktur / Sekundärstruktur INNERHALB einer Kopie).
  - selfDimer: zwei Kopien derselben mRNA lagern sich aneinander an
               (intermolekularer Duplex ZWISCHEN zwei Kopien).

Beide brauchen ViennaRNA (``pip install ViennaRNA``: siehe
Biologik/requirements.txt). Fehlt es, ist das kein Fehler: der Check wird
einfach ausgelassen, genau wie primer3 an anderer Stelle auf die
Wallace-Schaetzung zurueckfaellt: design_construct() liefert trotzdem ein
Ergebnis.

Eine rohe minimale freie Energie (MFE) allein ist zwischen Sequenzen nicht fair
vergleichbar: jede RNA hat allein durch Laenge und GC-Gehalt eine gewisse
Baseline-Faltungsenergie. Deshalb wird die MFE der echten Sequenz gegen den
Hintergrund mehrerer zufaellig durchmischter (basenzusammensetzungsgleicher)
Varianten derselben Sequenz verglichen: ein Z-Score, wie viele
Standardabweichungen die echte Sequenz staerker faltet/dimerisiert, als es
fuer eine zufaellige Sequenz derselben Zusammensetzung zu erwarten waere.
Deutlich negativer Z-Score = staerker strukturiert/selbstkomplementaer als
Zufall. Das Mischen ist ein einfaches Basen-Shuffle (nicht Dinukleotid-
erhaltend): eine bewusste Vereinfachung.

Das ist eine thermodynamische MFE-Abschaetzung, KEINE Bindungswahrscheinlichkeit
im kinetischen/Konzentrations-Sinn (dafuer fehlen intrazellulaere
Konzentrationen und Kinetik-Daten, die dieses Tool nicht hat).
"""

from __future__ import annotations


import random

# ViennaRNA-Aufrufe werden mit der Sequenzlaenge ungefaehr quadratisch
# langsamer. Real gemessen (RNA.fold + RNA.duplexfold zusammen, eine Sequenz):
#   500bp ~0.3s · 1000bp ~1.4s · 1500bp ~3.2s · 2000bp ~5.7s · 3000bp ~13.8s
# TARGET_SECONDS ist das Zeitbudget PRO Check (self-fold bzw. self-dimer,
# jeweils inkl. Zufalls-Hintergrund) — der Live-Check laeuft im Hintergrund
# nach einer Tipppause, nicht bei jedem Tastendruck, ein paar Sekunden
# Wartezeit fuer eine lange Sequenz sind hier in Ordnung.
TARGET_SECONDS = 10.0
# grober Kalibrierungsfaktor aus obigen Messungen (Sekunden pro bp^2), mit
# etwas Sicherheitsmarge nach oben, um das Budget nicht zu reissen
TIME_PER_BP2 = 1.6e-6
MIN_SHUFFLES = 2   # weniger als 2 ergibt keine sinnvolle Standardabweichung
MAX_SHUFFLES = 10  # mehr bringt bei kurzen Sequenzen kaum noch Praezision
MAX_LEN = 3000  # laenger: Check komplett uebersprungen (selbst 1x falten waere zu langsam)
SHUFFLE_SEED = 20260928  # deterministisch: dieselbe Sequenz -> dasselbe Ergebnis


def _estimated_seconds(length: int) -> float:
    return TIME_PER_BP2 * length * length


def _shuffle_count(length: int) -> int:
    """Wie viele Zufalls-Hintergrundsequenzen passen noch ins Zeitbudget?

    0 heisst: selbst 2 Shuffles wuerden das Budget reissen — dann gibt es nur
    die rohe MFE ohne Z-Score/Risikostufe. Kuerzere Sequenzen bekommen mehr
    Shuffles (bessere Statistik), laengere weniger, aber selten weniger als 2.
    """
    est = _estimated_seconds(length)
    if est <= 0:
        return MAX_SHUFFLES
    n = int(TARGET_SECONDS / est) - 1
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


def check_mrna_structure(sense_seq: str) -> dict:
    """``sense_seq``: eine validierte, fusionsbereite CDS in Sense-/Kodierrichtung
    (Cargo, eigene Shell oder eigenes Modul) — genau das ist auch die
    mRNA-Sequenz (mit U statt T)."""
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
    shuffles = _shuffle_count(len(rna))

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
