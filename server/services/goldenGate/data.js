/**
 * ENCORE Golden Gate — biological reference data & assembly constants.
 *
 * This is the single source of truth for the Golden Gate toolbox: the module
 * libraries the user picks from (decisions 1 + 2) and the fixed 4 nt fusion
 * overhangs that define how Level 0 parts ligate into Level 1 modules.
 *
 * Keep this file in sync with the prototype UI (frontend/encore-builder.html).
 * When the real toolbox parts / sequences are known they should move into the
 * database (see PROJECT_TODO.txt) — this file then becomes the seed data.
 */

/* ------------------------------------------------------------------ *
 * Golden Gate assembly constants
 * ------------------------------------------------------------------ */

/** The three stop codons — a cargo CDS must not end on one (see sequence.js). */
export const STOP_CODONS = ['TAA', 'TAG', 'TGA']

/**
 * Fixed 4 nt fusion overhangs per Level 0 slot (Type 1..5), as [5', 3'].
 * Adjacent slots share a fusion site, so the 3' overhang of slot n ligates to
 * the 5' overhang of slot n+1. These make the 5 Level 0 parts snap together
 * into one Level 1 module in a defined order.
 */
export const TYPE_OVERHANGS = {
  1: ['ACAT', 'ATAC'],
  2: ['TATG', 'AAGA'],
  3: ['TTCT', 'TAGG'],
  4: ['ATCC', 'ACCG'],
  5: ['TGGC', 'AACA'],
}

/** BsaI recognition site + spacer that precedes the overhang on every primer. */
export const BSAI_PRIMER_PREFIX = 'GGTCTCN'

/** Level 1 module flanks (the overhangs that fuse Level 1 -> Level 2). */
export const CARGO_L1_FLANK = ['CCAA', 'GCAA'] // cargo module
export const NC_L1_FLANK = ['TGAT', 'TTAC'] // nanocompartment module
export const PROMO_FLANK = ['CGTT', 'ACTA'] // bidirectional promoter

/** Nominal part lengths (bp) for the schematic map where no real CDS exists. */
export const NOMINAL_BP = {
  TP: 54, // targeting peptide
  PROMO: 680, // promoter
  NCS: 15, // NCS spacer / open surface slot
}

/* ------------------------------------------------------------------ *
 * Libraries (expandable — new entries can simply be appended, or later
 * loaded from the database; the dropdowns scale automatically)
 * ------------------------------------------------------------------ */

/**
 * Decision 1 — nanocompartment. Choosing one fixes the matching targeting
 * peptide (`tp`) and the shell CDS (`shell`) for the whole construct.
 */
export const NANOCOMPARTMENTS = [
  { id: 'tmari', label: 'Thermotoga maritima', T: 1, dia: '24 nm', tp: 'TP-Tm', shell: 'E-Tm', shellBp: 516 },
  { id: 'mxan', label: 'Myxococcus xanthus', T: 3, dia: '32 nm', tp: 'TP-Mx', shell: 'E-Mx', shellBp: 579 },
  { id: 'qther', label: 'Quasibacillus thermotolerans', T: 4, dia: '42 nm', tp: 'TP-Qt', shell: 'E-Qt', shellBp: 621 },
]

/** Decision 2 — cargo presets the user can load instead of pasting their own CDS. */
export const CARGO_PRESETS = [
  {
    id: 'gfp',
    label: 'GFP',
    seq:
      'ATGAGCAAAGGCGAAGAACTGTTTACCGGCGTTGTTCCGATTCTGGTTGAACTGGATGGCGATGTTAACGGCCATAAATTTAGCGTTAGCGGCGAAGGCGAAGGCGATGCGACCTATGGCAAACTGACCCTGAAATTTATTTGCACCACCGGCAAACTGCCGGTTCCGTGGCCGACCCTGGTTACCACCCTGAGC',
  },
  {
    id: 'pabp',
    label: 'PABP (Pab1p)',
    seq:
      'ATGGCAGATATTACCGAAAAACTGCTGGAACAGCTGAACAGCCTGACCCTGGAAGAAAGCAGCAAAGAAGTTAGCGGCGAACTGAGCGGCAAACTGGAAGCAAGCAGCAGCGAAAGCAGCGGC',
  },
]

/** Linker library (a linker is pre-made and lives in a Type 2 / Type 4 slot). */
export const LINKERS = [
  { id: 'GSSS2', label: '2×(GSSS)', aa: 8, bp: 24, desc: 'short · flexible', repeat: 'GSSS', n: 2, type: 'flexible' },
  { id: 'GSSS3', label: '3×(GSSS)', aa: 12, bp: 36, desc: 'medium · flexible', repeat: 'GSSS', n: 3, type: 'flexible' },
  { id: 'GGS2', label: '2×(GGS)', aa: 6, bp: 18, desc: 'short · very flexible', repeat: 'GGS', n: 2, type: 'flexible' },
]

/** Promoter library (currently one bidirectional promoter). */
export const PROMOTERS = [
  { id: 'GAL110', label: 'GAL1-10', desc: 'bidirectional, inducible' },
]

/* ------------------------------------------------------------------ *
 * Small lookup helpers
 * ------------------------------------------------------------------ */

export const findNanocompartment = (id) => NANOCOMPARTMENTS.find((n) => n.id === id) || null
export const findCargoPreset = (id) => CARGO_PRESETS.find((c) => c.id === id) || null
export const findLinker = (id) => LINKERS.find((l) => l.id === id) || null
export const findPromoter = (id) => PROMOTERS.find((p) => p.id === id) || null
