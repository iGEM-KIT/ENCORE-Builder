"""Codon optimization for Saccharomyces cerevisiae.

Every sequence entered by the user (cargo, own shell, own parts in the slots) is translated here and back-translated with the
codon usage of S. cerevisiae. The protein stays exactly the same.

Approach (like common tools, e.g. VectorBuilder): every codon is drawn at random, weighted by the natural
frequency in S. cerevisiae (to the power SHARPEN = 3, which matches the CAI/GC of VectorBuilder); rare codons (below 10 % of their
synonyms) are never used. This gives a high CAI (~0.85 to 0.9) at a natural GC content (~35 to 40 %) and without long runs of
identical codons. The randomness is tied to the input (seed = hash of the sequence), so the same input always gives the same output.

Afterwards an exact search (dynamic programming over all codons, not greedy) corrects the choice as little as possible, so that

* no BsaI site (GGTCTC / GAGACC) and no BbsI site (GAAGAC / GTCTTC) arises or remains, also not across the seam to the
  adapter (4-nt overhang + GC spacer + insert + overhang), so that the Golden Gate cloning does not cut the part; the same
  holds for the sites that the iGEM standards forbid inside a part: SapI (RFC 1000) and EcoRI, XbaI, SpeI, PstI plus NotI (RFC 10);
* no homopolymers of 7 or more identical bases arise (synthesis problems, for A/T in yeast also premature termination).

Codon usage: Kazusa table for S. cerevisiae (frequency per 1000 codons). CAI after Sharp & Li (1987) with
w = frequency / frequency of the most frequent synonymous codon.
"""

from __future__ import annotations

import hashlib
import random
from itertools import product
from math import exp, log

# Frequency per 1000 codons, S. cerevisiae (Kazusa, Codon Usage Database).
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
CODON_TABLE = {"".join(c): aa for c, aa in zip(product(_BASES, repeat=3), _AMINO)}

SYNONYMS: dict = {}
for _codon, _aa in CODON_TABLE.items():
    SYNONYMS.setdefault(_aa, []).append(_codon)

# Restriction sites that must never arise (both strands; a palindromic site is listed once).
#   BsaI, BbsI: the enzymes of this toolkit's Golden Gate assembly
#   SapI:       iGEM Type IIS standard RFC 1000 (together with BsaI)
#   EcoRI, XbaI, SpeI, PstI: BioBrick standard RFC 10 (illegal in a part); NotI is listed there as "avoid"
# Source: the iGEM Registry help pages "Help:Standards/Assembly/Type_IIS" and "Help:Standards/Assembly/RFC10".
FORBIDDEN_SITES = {
    "BsaI": ("GGTCTC", "GAGACC"),
    "BbsI": ("GAAGAC", "GTCTTC"),
    "SapI": ("GCTCTTC", "GAAGAGC"),
    "EcoRI": ("GAATTC",),
    "XbaI": ("TCTAGA",),
    "SpeI": ("ACTAGT",),
    "PstI": ("CTGCAG",),
    "NotI": ("GCGGCCGC",),
}
_FORBIDDEN = tuple(s for sites in FORBIDDEN_SITES.values() for s in sites)
# Bases of context kept on each side: the longest site minus one, so a site that spans a seam is always seen
CONTEXT = max(len(s) for s in _FORBIDDEN) - 1
MAX_RUN = 6  # longest allowed homopolymer
# Exponent on the frequency in the random draw (1 = proportional); 3 matches CAI/GC of VectorBuilder (~0.87 / ~36 %)
SHARPEN = 3.0
# From this CAI on, a sequence without sites or runs stays unchanged (like VectorBuilder)
ALREADY_ADAPTED_CAI = 0.85
# Codons below 10 % of the usage of their amino acid are never chosen
MIN_SHARE = 0.10

# w = relative adaptiveness (most frequent synonymous codon = 1)
W = {c: CODON_USAGE[c] / max(CODON_USAGE[s] for s in SYNONYMS[CODON_TABLE[c]]) for c in CODON_TABLE}
BEST_CODON = {aa: max(codons, key=CODON_USAGE.get) for aa, codons in SYNONYMS.items()}
# Synonymous codons per amino acid without the rare ones (below MIN_SHARE of the total usage of the amino acid)
_USABLE = {aa: [c for c in codons if CODON_USAGE[c] / sum(CODON_USAGE[s] for s in codons) >= MIN_SHARE]
           for aa, codons in SYNONYMS.items()}


def back_translate(protein: str) -> str:
    """Amino acid sequence -> DNA with the most frequent yeast codon each (starting point for the optimization; a '*' becomes TAA)."""
    return "".join(BEST_CODON[aa] for aa in protein)


def translate(dna: str) -> str:
    return "".join(CODON_TABLE.get(dna[i:i + 3], "X") for i in range(0, len(dna) - len(dna) % 3, 3))


def cai(dna: str) -> float:
    """Codon adaptation index (geometric mean of the w values, without ATG/TGG, which have no choice, and without stop codons)."""
    ws = [W[dna[i:i + 3]] for i in range(0, len(dna) - len(dna) % 3, 3)
          if CODON_TABLE[dna[i:i + 3]] not in ("M", "W", "*")]
    return exp(sum(log(w) for w in ws) / len(ws)) if ws else 1.0


def gc_percent(dna: str) -> float:
    return 100.0 * sum(1 for b in dna if b in "GC") / len(dna) if dna else 0.0


def find_forbidden(dna: str) -> list:
    """All forbidden restriction sites (enzyme, 0-based position, site) in a sequence."""
    hits = []
    for enzyme, sites in FORBIDDEN_SITES.items():
        for site in sites:
            start = dna.find(site)
            while start != -1:
                hits.append({"enzyme": enzyme, "pos": start, "site": site})
                start = dna.find(site, start + 1)
    return sorted(hits, key=lambda h: h["pos"])


def _has_run(dna: str) -> bool:
    return any(len(set(dna[i:i + MAX_RUN + 1])) == 1 for i in range(len(dna) - MAX_RUN))


def _bad(window: str, tail_len: int) -> bool:
    """Does `window` (context + new codon; the last `tail_len` bases are new) contain a forbidden motif that
        touches at least one new base?"""
    n = len(window)
    for site in _FORBIDDEN:
        for end in range(n - tail_len + 1, n + 1):  # site ends in the new bases
            if end - len(site) >= 0 and window[end - len(site):end] == site:
                return True
    run = MAX_RUN + 1
    for end in range(n - tail_len + 1, n + 1):
        if end - run >= 0 and len(set(window[end - run:end])) == 1:
            return True
    return False


def _crosses(window: str, split: int) -> bool:
    """Does `window` contain a forbidden site that spans the position `split` (bases on both sides)?"""
    for site in _FORBIDDEN:
        for start in range(max(0, split - len(site) + 1), min(split, len(window) - len(site) + 1)):
            if window[start:start + len(site)] == site:
                return True
    return False


def _cost(codon: str, target: str) -> float:
    """Cost of deviating from the target codon: 0 for the target codon, otherwise 1 (with the same number of deviations the more frequent
        codon wins); a rare codon (below MIN_SHARE) costs 5 extra, so it is only chosen when there is no other way."""
    if codon == target:
        return 0.0
    rare = codon not in _USABLE[CODON_TABLE[codon]]
    return 1.0 + 0.1 * (1.0 - W[codon]) + (5.0 if rare else 0.0)


def _as_list(value) -> list:
    return [value] if isinstance(value, str) else list(value or [""])


def _sites_in_context(seq: str, lefts: list, rights: list) -> list:
    """Forbidden sites in `seq` including all neighbour contexts (every left/right variant), without duplicates."""
    seen, hits = set(), []
    for left in lefts:
        for right in rights:
            for h in find_forbidden(left[-CONTEXT:] + seq + right[:CONTEXT]):
                key = (h["enzyme"], h["pos"] - len(left[-CONTEXT:]), h["site"])
                if key not in seen:
                    seen.add(key)
                    hits.append({**h, "pos": h["pos"] - len(left[-CONTEXT:])})
    return sorted(hits, key=lambda h: h["pos"])


def _draw_targets(dna: str) -> list:
    """The randomly drawn target codon per position (seed = input, so reproducible); stop codons stay as entered."""
    rng = random.Random(hashlib.sha256(dna.encode()).digest())
    targets = []
    for i in range(0, len(dna), 3):
        codon = dna[i:i + 3]
        aa = CODON_TABLE[codon]
        if aa == "*":
            targets.append(codon)
        else:
            pool = _USABLE[aa]
            targets.append(rng.choices(pool, weights=[CODON_USAGE[c] ** SHARPEN for c in pool])[0])
    return targets


def _search(dna: str, targets: list, lefts: list, rights: list) -> tuple:
    """Exact search (dynamic programming) for the codons that deviate as little as possible from the target codons and
        form no forbidden site. State = the last CONTEXT bases per context variant. Returns (sequence, None) or (None, reason)."""
    layers = []  # per position: state -> (score, predecessor state, codon) for the traceback
    states = {tuple(left[-CONTEXT:] for left in lefts): 0.0}
    for i, target in enumerate(targets):
        original = dna[3 * i:3 * i + 3]
        options = SYNONYMS[CODON_TABLE[original]] if CODON_TABLE[original] != "*" else [original]
        nxt = {}
        for state, score in states.items():
            for codon in options:
                windows = tuple(w + codon for w in state)
                if any(_bad(w, 3) for w in windows):
                    continue
                key = tuple(w[-CONTEXT:] for w in windows)
                s = score - _cost(codon, target)
                if key not in nxt or s > nxt[key][0]:
                    nxt[key] = (s, state, codon)
        if not nxt:  # nothing allowed (cannot happen in practice)
            return None, "No codon combination avoids all restriction sites."
        layers.append(nxt)
        states = {k: v[0] for k, v in nxt.items()}

    # Right context: no site may arise across the seam to the adapter either.
    finals = [(score, key) for key, score in states.items()
              if not any(_crosses(w[-CONTEXT:] + r[:CONTEXT], len(w[-CONTEXT:])) for w in key for r in rights)]
    if not finals:
        return None, "No codon combination avoids all restriction sites at the right junction."
    key = max(finals)[1]
    codons = []
    for layer in reversed(layers):
        _, prev, codon = layer[key]
        codons.append(codon)
        key = prev
    return "".join(reversed(codons)), None


def optimize_cds(dna: str, left="", right="", protein: bool = False) -> dict:
    """Codon-optimizes a CDS (sense strand, 5'->3', without a stop codon at the end) for S. cerevisiae.

        `left`/`right` is the fixed neighbour context (adapter flank, sense direction) left and right of the insert, so that no
        site arises across the seam. Instead of a string a list of variants is also accepted (e.g. Level 0 adapter and the
        neighbour in the Level 1 module); the sequence is then free of sites against all of them. The protein stays unchanged; stop codons
        the user entered in the middle of the sequence stay as entered.

        With `protein=True`, `dna` is an amino acid sequence: it is translated into DNA with the codon table (same choice and same
        rules as otherwise); there are no "before" values (CAI, GC, sites) then, and `fromProtein` is True.

        Result: dict with `status` ("optimized", "kept" or "skipped", then with `reason`), `sequence`, `changed` (number of changed
        codons), `codons`, CAI/GC before/after, `forbiddenBefore` (forbidden sites in the input) and `forbiddenAfter` (with
        context, should be empty)."""
    dna = (dna or "").upper()
    if protein:
        dna = back_translate(dna)
    lefts, rights = _as_list(left), _as_list(right)
    cai_before = cai(dna) if len(dna) >= 3 else 1.0
    gc_before = gc_percent(dna)
    sites_before = [] if protein or not dna else _sites_in_context(dna, lefts, rights)
    result = {"status": "skipped", "fromProtein": protein, "sequence": dna, "optimized": False, "changed": 0,
              "codons": len(dna) // 3, "caiBefore": None if protein else round(cai_before, 3),
              "gcBefore": None if protein else round(gc_before, 1), "caiAfter": round(cai_before, 3),
              "gcAfter": round(gc_before, 1), "forbiddenBefore": sites_before, "forbiddenAfter": []}
    if len(dna) < 3 or len(dna) % 3:
        return {**result, "reason": "Length is not a multiple of 3; the sequence was kept as entered."}
    if not protein and cai_before >= ALREADY_ADAPTED_CAI and not sites_before and not _has_run(dna):
        return {**result, "status": "kept", "optimized": True,
                "reason": f"Already well adapted to S. cerevisiae (CAI {result['caiBefore']}) and free of the restriction sites to avoid (BsaI, BbsI, SapI, EcoRI, XbaI, SpeI, PstI, NotI); kept as entered."}

    out, reason = _search(dna, _draw_targets(dna), lefts, rights)
    if out is None:
        return {**result, "reason": reason}
    changed = 0 if protein else sum(1 for i in range(0, len(dna), 3) if out[i:i + 3] != dna[i:i + 3])
    return {**result, "sequence": out, "status": "optimized", "optimized": True, "changed": changed,
            "caiAfter": round(cai(out), 3), "gcAfter": round(gc_percent(out), 1),
            "forbiddenAfter": _sites_in_context(out, lefts, rights)}


def remove_forbidden_sites(dna: str, left="", right="") -> dict:
    """Removes only the forbidden sites (FORBIDDEN_SITES) from a CDS, with as few synonymous codon changes as possible: the target of
    every codon is the codon it already has, so that nothing else changes (for parts that are not meant to be optimized, such as the
    NCS spacers of the toolKIT). A sequence without such a site is returned unchanged. Same result format as `optimize_cds`;
    `siteFix` is True."""
    dna = (dna or "").upper()
    lefts, rights = _as_list(left), _as_list(right)
    before = _sites_in_context(dna, lefts, rights) if dna else []
    result = {"status": "kept", "fromProtein": False, "sequence": dna, "optimized": False, "changed": 0, "codons": len(dna) // 3,
              "caiBefore": round(cai(dna), 3) if len(dna) >= 3 else 1.0, "caiAfter": round(cai(dna), 3) if len(dna) >= 3 else 1.0,
              "gcBefore": round(gc_percent(dna), 1), "gcAfter": round(gc_percent(dna), 1), "forbiddenBefore": before, "forbiddenAfter": before,
              "siteFix": True, "reason": "No restriction site to avoid; kept as it is."}
    if len(dna) < 3 or len(dna) % 3:
        return {**result, "status": "skipped", "reason": "Length is not a multiple of 3; the sequence was kept as it is."}
    if not before:
        return result
    out, reason = _search(dna, [dna[i:i + 3] for i in range(0, len(dna), 3)], lefts, rights)
    if out is None:
        return {**result, "status": "skipped", "reason": reason}
    changed = sum(1 for i in range(0, len(dna), 3) if out[i:i + 3] != dna[i:i + 3])
    return {**result, "sequence": out, "status": "optimized", "optimized": True, "changed": changed,
            "caiAfter": round(cai(out), 3), "gcAfter": round(gc_percent(out), 1), "forbiddenAfter": _sites_in_context(out, lefts, rights)}
