from __future__ import annotations

"""Statische Daten und Konstanten für das Level-0-Design."""

# Stop-Codons: Diese Tripletts markieren das Ende einer Proteinkodierung, STOP_CODONS ist eine Variable
STOP_CODONS = ["TAA", "TAG", "TGA"]

# Feste 4-Basen-Overhangs für die Assemblierung der Level-0-Teile.
# Dictionary speichert Daten in Form von Schlüssel-Wert-Paaren
# Für jeden Typ (1-5) gibt es eine Liste von zwei Overhangs, die für die Assemblierung verwendet werden.
# Verbindungsteile der Level0 Module

TYPE_OVERHANGS = {
    1: ["ACAT", "ATAC"],
    2: ["TATG", "AAGA"],
    3: ["TTCT", "TAGG"],
    4: ["ATCC", "ACCG"],
    5: ["TGGC", "AACA"],
}

# Die sechs Nahtstellen (Top-Strand) zwischen den Typen: Typ n reicht von JUNCTION_OVERHANGS[n-1]
# bis JUNCTION_OVERHANGS[n]. TYPE_OVERHANGS oben nennt als 3'-Wert das Komplement der naechsten
# Nahtstelle (so wie es auf dem Gegenstrang steht) — fuer echte Sequenzen zaehlen diese Werte.
JUNCTION_OVERHANGS = ["ACAT", "TATG", "TTCT", "ATCC", "TGGC", "TTGT"]

# Definition des Anfangsteils eines Primers, der für Assemblierung benötigt wird. 
# Dieser ist beim Golden Gate Assembly für alle Primer gleich und wird hier als Konstante gespeichert.

BSAI_PRIMER_PREFIX = "GGTCTCN"

CARGO_L1_FLANK = ["CCAA", "GCAA"]
NC_L1_FLANK = ["TGAT", "TTAC"]
PROMO_FLANK = ["CGTT", "ACTA"]

# Näherungswerte für die Länge einzelner Bausteine in Basenpaaren (bp), nicht echte biologische Länge
# Wenn ein Modul gebaut wird, weiß das Programm ungefähr, wie viele Basenpaare es hat, und kann die
# Gesamtzahl der Basenpaare einfacher berechnen.
# Auch für die Anzeige des Plasmids in der Benutzeroberfläche ist es praktisch.

NOMINAL_BP = {
    "TP": 54,
    "PROMO": 680,
    "NCS": 15,
}

# Bibliotheken für Nanokompartimente
# Jedes vordefinierte Nanokompartment hat: ID (interne Kommunikation); Label (angezeigt in der Benutzeroberfäche);
# Temperatur T; Durchmesser dia; Targeting Peptide tp; Protein, aus dem Nanokompartment Hülle besteht Shell 

NANOCOMPARTMENTS = [
    {"id": "tmari", "label": "Thermotoga maritima", "T": 1, "dia": "24 nm", "tp": "TP-Tm", "shell": "E-Tm", "shellBp": 516},
    {"id": "mxan", "label": "Myxococcus xanthus", "T": 3, "dia": "32 nm", "tp": "TP-Mx", "shell": "E-Mx", "shellBp": 579},
    {"id": "qther", "label": "Quasibacillus thermotolerans", "T": 4, "dia": "42 nm", "tp": "TP-Qt", "shell": "E-Qt", "shellBp": 621},
]

# Bibliothek für Cargo-Vorlagen, also beispielhafte Gene of Interest Sequenzen, die ins Plasmid eingebaut werden können.
# Welche Beispiele für Cargo-Sequenzen sollen wir hier aufnehmen?

CARGO_PRESETS = [
    {
        "id": "gfp",
        "label": "GFP",
        "seq": "ATGAGCAAAGGCGAAGAACTGTTTACCGGCGTTGTTCCGATTCTGGTTGAACTGGATGGCGATGTTAACGGCCATAAATTTAGCGTTAGCGGCGAAGGCGAAGGCGATGCGACCTATGGCAAACTGACCCTGAAATTTATTTGCACCACCGGCAAACTGCCGGTTCCGTGGCCGACCCTGGTTACCACCCTGAGC",
    },
    {
        "id": "pabp",
        "label": "PABP (Pab1p)",
        "seq": "ATGGCAGATATTACCGAAAAACTGCTGGAACAGCTGAACAGCCTGACCCTGGAAGAAAGCAGCAAAGAAGTTAGCGGCGAACTGAGCGGCAAACTGGAAGCAAGCAGCAGCGAAAGCAGCGGC",
    },
]

# Bibliothek für Linker mit Aminosäuren aa; kurze Beschreibungdesc; Wiederholungssequenz gibt an, welche Sequenz wiederholt wird repeat;
# Wiederholungssequenz beschreibt, aus welchen Bausteinen er augebaut ist
# Anzahl der Sequenz-Wiederholungen n; Art des Linkers, also biologische Eigenschaften beeinflussen, wie gut Linker zu Anwendung passt, type
LINKERS = [
    {"id": "GSSS2", "label": "2×(GSSS)", "aa": 8, "bp": 24, "desc": "short · flexible", "repeat": "GSSS", "n": 2, "type": "flexible"},
    {"id": "GSSS3", "label": "3×(GSSS)", "aa": 12, "bp": 36, "desc": "medium · flexible", "repeat": "GSSS", "n": 3, "type": "flexible"},
    {"id": "GGS2", "label": "2×(GGS)", "aa": 6, "bp": 18, "desc": "short · very flexible", "repeat": "GGS", "n": 2, "type": "flexible"},
]

# Bibliothek für Promotoren
PROMOTERS = [{"id": "GAL110", "label": "GAL1-10", "desc": "bidirectional, inducible"}]

# Oberflaechen-Marker. Sie lassen sich in einen der Slots neben der Shell legen
# (Type 1, 2, 4, 5) und sitzen dadurch AUSSEN auf dem Encapsulin — im Gegensatz
# zum Cargo, das innen verpackt wird.
SURFACE_MARKERS = [
    {"id": "spycatcher", "label": "SpyCatcher", "aa": 113, "bp": 339, "desc": "covalent SpyTag capture (isopeptide bond)"},
    {"id": "spytag", "label": "SpyTag", "aa": 13, "bp": 39, "desc": "13-aa peptide, binds SpyCatcher"},
]

# Alles, was das Frontend für seine Dropdowns braucht — an EINER Stelle.
# Bewusst eine Funktion und keine Konstante, damit sie später aus der Datenbank
# lesen kann, ohne dass sich die Aufrufer ändern (siehe PROJECT_TODO.txt, 5).

def get_libraries() -> dict:
    return {
        "nanocompartments": NANOCOMPARTMENTS,
        "cargoPresets": CARGO_PRESETS,
        "linkers": LINKERS,
        "promoters": PROMOTERS,
        "surfaceMarkers": SURFACE_MARKERS,
        "typeOverhangs": TYPE_OVERHANGS,
    }


# Suchfunktionen für die Bibliotheken, um ein Element anhand seiner ID zu finden.

def find_nanocompartment(identifier: str):
    # next(...) sucht das erste passende Element und gibt es zurück.
    return next((item for item in NANOCOMPARTMENTS if item["id"] == identifier), None)


def find_cargo_preset(identifier: str):
    return next((item for item in CARGO_PRESETS if item["id"] == identifier), None)


def find_linker(identifier: str):
    return next((item for item in LINKERS if item["id"] == identifier), None)


def find_promoter(identifier: str):
    return next((item for item in PROMOTERS if item["id"] == identifier), None)


def find_surface_marker(identifier: str):
    return next((item for item in SURFACE_MARKERS if item["id"] == identifier), None)
