from __future__ import annotations

"""Codon-Optimierung fuer Saccharomyces cerevisiae.

Jede vom Nutzer eingegebene Sequenz (Cargo, eigene Shell, eigene Teile in den Slots) wird hier uebersetzt und mit der
Codon-Nutzung von S. cerevisiae zurueckuebersetzt. Das Protein bleibt dabei exakt gleich.

Vorgehen (wie gaengige Tools, z.B. VectorBuilder): Jedes Codon wird zufaellig gezogen, gewichtet mit der natuerlichen
Haeufigkeit in S. cerevisiae (hoch SHARPEN = 3, das trifft CAI/GC von VectorBuilder), seltene Codons (unter 10 % der Synonyme) werden nie benutzt. Das ergibt einen hohen CAI (~0.85-0.9) bei
natuerlichem GC-Gehalt (~35-40 %) und ohne lange Wiederholungen identischer Codons. Der Zufall ist an die Eingabe gekoppelt
(Seed = Hash der Sequenz), dieselbe Eingabe gibt also immer dieselbe Ausgabe.

Danach wird mit einer exakten Suche (Dynamic Programming ueber alle Codons, nicht gierig) die Auswahl so wenig wie moeglich
korrigiert, damit

* keine BsaI-Stelle (GGTCTC / GAGACC) und keine BbsI-Stelle (GAAGAC / GTCTTC) entsteht oder bleibt, auch nicht ueber die Naht zum
  Adapter hinweg (4-nt-Overhang + GC-Spacer + Insert + Overhang), damit das Golden-Gate-Klonieren nicht zerschneidet;
* keine Homopolymere ab 7 gleichen Basen entstehen (Syntheseprobleme, bei A/T in Hefe zusaetzlich vorzeitige Termination).

Codon-Nutzung: Kazusa-Tabelle fuer S. cerevisiae (Haeufigkeit pro 1000 Codons). CAI nach Sharp & Li (1987) mit
w = Haeufigkeit / Haeufigkeit des haeufigsten synonymen Codons.
"""

import hashlib
import random
from collections import defaultdict
from math import exp, log

# Haeufigkeit pro 1000 Codons, S. cerevisiae (Kazusa, Codon Usage Database).
CODON_USAGE = {
    "TTT": 26.1, "TTC": 18.4, "TTA": 26.2, "TTG": 27.2,
    "CTT": 12.3, "CTC": 5.4, "CTA": 13.4, "CTG": 10.5,
    "ATT": 30.1, "ATC": 17.2, "ATA": 17.8, "ATG": 20.9,
    "GTT": 22.1, "GTC": 11.8, "GTA": 11.8, "GTG": 10.8,
    "TCT": 23.5, "TCC": 14.2, "TCA": 18.7, "TCG": 8.6,
    "CCT": 13.5, "CCC": 6.8, "CCA": 18.3, "CCG": 5.3,
    "ACT": 20.3, "ACC": 12.7, "ACA": 17.8, "ACG": 8.0,
    "GCT": 21.2, "GCC": 12.6, "GCA": 16.2, "GCG": 6.2,
    "TAT": 18.8, "TAC": 14.8, "TAA": 1.1, "TAG": 0.5,
    "CAT": 13.6, "CAC": 7.8, "CAA": 27.3, "CAG": 12.1,
    "AAT": 35.7, "AAC": 24.8, "AAA": 41.9, "AAG": 30.8,
    "GAT": 37.6, "GAC": 20.2, "GAA": 45.6, "GAG": 19.2,
    "TGT": 8.1, "TGC": 4.8, "TGA": 0.7, "TGG": 10.4,
    "CGT": 6.4, "CGC": 2.6, "CGA": 3.0, "CGG": 1.7,
    "AGT": 14.2, "AGC": 9.8, "AGA": 21.3, "AGG": 9.2,
    "GGT": 23.9, "GGC": 9.8, "GGA": 10.9, "GGG": 6.0,
}

_BASES = "TCAG"
_AMINO = "FFLLSSSSYY**CC*WLLLLPPPPHHQQRRRRIIIMTTTTNNKKSSRRVVVVAAAADDEEGGGG"
CODON_TABLE = {a + b + c: _AMINO[i] for i, (a, b, c) in enumerate((a, b, c) for a in _BASES for b in _BASES for c in _BASES)}

SYNONYMS: dict = defaultdict(list)
for _codon, _aa in CODON_TABLE.items():
    SYNONYMS[_aa].append(_codon)
# w = relative Adaptiertheit (haeufigstes synonymes Codon = 1)
W = {c: CODON_USAGE[c] / max(CODON_USAGE[s] for s in SYNONYMS[CODON_TABLE[c]]) for c in CODON_TABLE}

# Restriktionsstellen, die nie entstehen duerfen (beide Straenge).
FORBIDDEN_SITES = {"BsaI": ("GGTCTC", "GAGACC"), "BbsI": ("GAAGAC", "GTCTTC")}
_FORBIDDEN = tuple(s for pair in FORBIDDEN_SITES.values() for s in pair)
MAX_RUN = 6                      # laengstes erlaubtes Homopolymer
SHARPEN = 3.0                    # Exponent auf die Haeufigkeit bei der Zufallswahl (1 = proportional); 3 trifft CAI/GC von VectorBuilder (~0.87 / ~36 %)
ALREADY_ADAPTED_CAI = 0.85       # ab diesem CAI bleibt eine Sequenz, die sonst keine Stelle/Wiederholung hat, unveraendert (wie bei VectorBuilder)
MIN_SHARE = 0.10                 # Codons mit weniger als 10 % der synonymen Nutzung werden nie gewaehlt


def _usable(aa: str) -> list:
    """Synonyme Codons einer Aminosaeure ohne die seltenen (unter MIN_SHARE der Gesamtnutzung der Aminosaeure)."""
    total = sum(CODON_USAGE[c] for c in SYNONYMS[aa])
    return [c for c in SYNONYMS[aa] if CODON_USAGE[c] / total >= MIN_SHARE]


def back_translate(protein: str) -> str:
    """Aminosaeurefolge -> DNA mit dem jeweils haeufigsten Hefe-Codon (Ausgangspunkt fuer die Optimierung; ein '*' wird TAA)."""
    best = {aa: max(SYNONYMS[aa], key=CODON_USAGE.get) for aa in SYNONYMS}
    return "".join(best[aa] for aa in protein)


def translate(dna: str) -> str:
    return "".join(CODON_TABLE.get(dna[i:i + 3], "X") for i in range(0, len(dna) - len(dna) % 3, 3))


def cai(dna: str) -> float:
    """Codon Adaptation Index (geometrisches Mittel der w-Werte, ohne ATG/TGG, die keine Wahl haben, und ohne Stopcodons)."""
    ws = [W[dna[i:i + 3]] for i in range(0, len(dna) - len(dna) % 3, 3)
          if CODON_TABLE[dna[i:i + 3]] not in ("M", "W", "*")]
    return exp(sum(log(w) for w in ws) / len(ws)) if ws else 1.0


def gc_percent(dna: str) -> float:
    return 100.0 * sum(1 for b in dna if b in "GC") / len(dna) if dna else 0.0


def find_forbidden(dna: str) -> list:
    """Alle verbotenen Restriktionsstellen (Enzym, Position 0-basiert, Stelle) in einer Sequenz."""
    hits = []
    for enzyme, sites in FORBIDDEN_SITES.items():
        for site in sites:
            start = dna.find(site)
            while start != -1:
                hits.append({"enzyme": enzyme, "pos": start, "site": site})
                start = dna.find(site, start + 1)
    return sorted(hits, key=lambda h: h["pos"])


def _bad(window: str, tail_len: int) -> bool:
    """Enthaelt `window` (Kontext + neues Codon; die letzten `tail_len` Basen sind neu) ein verbotenes Motiv, das
    mindestens eine neue Base beruehrt?"""
    n = len(window)
    for site in _FORBIDDEN:
        for end in range(n - tail_len + 1, n + 1):          # Stelle endet in den neuen Basen
            if end - len(site) >= 0 and window[end - len(site):end] == site:
                return True
    run = MAX_RUN + 1
    for end in range(n - tail_len + 1, n + 1):
        if end - run >= 0 and len(set(window[end - run:end])) == 1:
            return True
    return False


def _cost(codon: str, target: str) -> float:
    """Kosten, vom Wunsch-Codon abzuweichen: 0 beim Wunsch-Codon, sonst 1 (bei gleicher Anzahl Abweichungen gewinnt das haeufigere
    Codon); ein seltenes Codon (unter MIN_SHARE) kostet zusaetzlich 5, wird also nur gewaehlt, wenn es nicht anders geht."""
    if codon == target:
        return 0.0
    aa = CODON_TABLE[codon]
    rare = aa != "*" and codon not in _usable(aa)
    return 1.0 + 0.1 * (1.0 - W[codon]) + (5.0 if rare else 0.0)


def _crosses(window: str, split: int) -> bool:
    """Enthaelt `window` eine verbotene Stelle, die die Position `split` ueberspannt (Basen auf beiden Seiten)?"""
    for site in _FORBIDDEN:
        for start in range(max(0, split - len(site) + 1), min(split, len(window) - len(site) + 1)):
            if window[start:start + len(site)] == site:
                return True
    return False


def _as_list(value) -> list:
    return [value] if isinstance(value, str) else list(value or [""])


def _sites_in_context(seq: str, lefts: list, rights: list) -> list:
    """Verbotene Stellen in `seq` samt allen Nachbarkontexten (jede Links-/Rechts-Variante), ohne Doppelte."""
    seen, hits = set(), []
    for left in lefts:
        for right in rights:
            for h in find_forbidden(left[-5:] + seq + right[:5]):
                key = (h["enzyme"], h["pos"] - len(left[-5:]), h["site"])
                if key not in seen:
                    seen.add(key)
                    hits.append({**h, "pos": h["pos"] - len(left[-5:])})
    return sorted(hits, key=lambda h: h["pos"])


def optimize_cds(dna: str, left="", right="", protein: bool = False) -> dict:
    """Codon-optimiert eine CDS (Sense-Strang, 5'->3', ohne Stopcodon am Ende) fuer S. cerevisiae.

    `left`/`right` ist der feste Nachbarkontext (Adapter-Flanke, Sense-Richtung) links bzw. rechts vom Insert, damit keine
    Stelle ueber die Naht hinweg entsteht. Statt eines Strings geht auch eine Liste von Varianten (z.B. Level-0-Adapter und der
    Nachbar im Level-1-Modul); die Sequenz ist dann gegen alle frei von Stellen. Das Protein bleibt unveraendert; Stopcodons, die
    der Nutzer mitten in der Sequenz eingegeben hat, bleiben wie eingegeben.

    Mit `protein=True` ist `dna` eine Aminosaeurefolge: sie wird mit der Codon-Tabelle in DNA uebersetzt (gleiche Wahl und gleiche
    Regeln wie sonst); "vorher"-Werte (CAI, GC, Stellen) gibt es dann nicht, und `fromProtein` ist True.

    Ergebnis: dict mit `sequence`, `changed` (Anzahl geaenderter Codons), `codons`, CAI/GC vorher/nachher, `forbiddenBefore`
    (verbotene Stellen in der Eingabe), `forbiddenAfter` (mit Kontext, sollte leer sein) und `optimized` (False, wenn die
    Sequenz nicht optimiert werden konnte, mit `reason`)."""
    dna = (dna or "").upper()
    if protein:
        dna = back_translate(dna)
    lefts, rights = _as_list(left), _as_list(right)
    before = {"cai": cai(dna) if len(dna) >= 3 else 1.0, "gc": gc_percent(dna)}
    base = {"status": "skipped", "fromProtein": protein, "original": None if protein else dna, "sequence": dna, "optimized": False, "changed": 0, "codons": len(dna) // 3,
            "protein": translate(dna), "caiBefore": round(before["cai"], 3), "gcBefore": round(before["gc"], 1),
            "caiAfter": round(before["cai"], 3), "gcAfter": round(before["gc"], 1),
            "forbiddenBefore": [] if protein else (_sites_in_context(dna, lefts, rights) if dna else []), "forbiddenAfter": []}
    if protein:
        base.update({"caiBefore": None, "gcBefore": None})
    if len(dna) < 3 or len(dna) % 3:
        return {**base, "reason": "Length is not a multiple of 3; the sequence was kept as entered."}

    n = len(dna) // 3
    has_run = any(len(set(dna[i:i + MAX_RUN + 1])) == 1 for i in range(len(dna) - MAX_RUN))
    if not protein and before["cai"] >= ALREADY_ADAPTED_CAI and not base["forbiddenBefore"] and not has_run:
        return {**base, "status": "kept", "optimized": True,
                "reason": f"Already well adapted to S. cerevisiae (CAI {base['caiBefore']}) and free of BsaI/BbsI sites; kept as entered."}
    rng = random.Random(hashlib.sha256(dna.encode()).digest())      # Seed = Eingabe -> reproduzierbar
    targets = []                                                    # pro Position das zufaellig gezogene Wunsch-Codon
    for i in range(n):
        aa = CODON_TABLE[dna[3 * i:3 * i + 3]]
        if aa == "*":
            targets.append(dna[3 * i:3 * i + 3])
        else:
            pool = _usable(aa)
            targets.append(rng.choices(pool, weights=[CODON_USAGE[c] ** SHARPEN for c in pool])[0])

    # Zustand = die letzten 6 Basen je Kontextvariante. Pro Schritt: Zustand -> (Score, Vorgaenger-Zustand, Codon) fuer die Rueckverfolgung.
    layers = []
    states = {tuple(l[-6:] for l in lefts): 0.0}
    for i in range(n):
        original = dna[3 * i:3 * i + 3]
        options = SYNONYMS[CODON_TABLE[original]] if CODON_TABLE[original] != "*" else [original]
        nxt = {}
        for state, score in states.items():
            for codon in options:
                windows = tuple(w + codon for w in state)
                if any(_bad(w, 3) for w in windows):
                    continue
                key = tuple(w[-6:] for w in windows)
                s = score - _cost(codon, targets[i])
                if key not in nxt or s > nxt[key][0]:
                    nxt[key] = (s, state, codon)
        if not nxt:                                 # nichts erlaubt (kann in der Praxis nicht passieren)
            return {**base, "reason": "No codon combination avoids all restriction sites."}
        layers.append(nxt)
        states = {k: v[0] for k, v in nxt.items()}

    # Rechter Kontext: auch ueber die Naht zum Adapter darf keine Stelle entstehen.
    finals = [(score, key) for key, score in states.items()
              if not any(_crosses(w[-5:] + r[:5], len(w[-5:])) for w in key for r in rights)]
    if not finals:
        return {**base, "reason": "No codon combination avoids all restriction sites at the right junction."}
    key = max(finals)[1]
    codons = []
    for layer in reversed(layers):
        _, prev, codon = layer[key]
        codons.append(codon)
        key = prev
    out = "".join(reversed(codons))
    changed = 0 if protein else sum(1 for i in range(n) if out[3 * i:3 * i + 3] != dna[3 * i:3 * i + 3])
    return {**base, "sequence": out, "status": "optimized", "optimized": True, "changed": changed,
            "caiAfter": round(cai(out), 3), "gcAfter": round(gc_percent(out), 1),
            "forbiddenAfter": _sites_in_context(out, lefts, rights)}
