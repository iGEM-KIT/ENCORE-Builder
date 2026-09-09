/**
 * ENCORE Golden Gate — design engine.
 *
 * Turns the three user decisions into a full Golden Gate assembly plan:
 *
 *   Decision 1  nanocompartment  ->  targeting peptide + shell (fixed)
 *   Decision 2  cargo CDS        ->  the one part the user actually orders
 *   Decision 3  C-/N-terminal    ->  arrangement of the 5 Level 0 slots
 *
 * Output hierarchy:
 *   Level 0 : 10 individual parts (5 for the cargo module, 5 for the NC module),
 *             each with its fixed Type 1..5 fusion overhangs.
 *   Level 1 : 2 assembled modules (cargo module, NC module).
 *   Level 2 : cargo module  <- promoter ->  NC module  (bidirectional).
 *
 * This is a pure, dependency-free port of the prototype logic
 * (frontend/encore-builder.html) so the same result can be produced server-side.
 */

import {
  BSAI_PRIMER_PREFIX,
  CARGO_L1_FLANK,
  LINKERS,
  NC_L1_FLANK,
  NOMINAL_BP,
  PROMO_FLANK,
  TYPE_OVERHANGS,
  findLinker,
  findNanocompartment,
  findPromoter,
} from './data.js'
import { reverseComplement, validateCargo, wallaceTm } from './sequence.js'

/**
 * @typedef {Object} Decisions
 * @property {string} nanocompartment  Nanocompartment id (decision 1)
 * @property {string} cargoSeq         Raw cargo CDS (decision 2)
 * @property {string} [cargoLabel]     Optional display label for the cargo
 * @property {'C'|'N'} fusion          Fusion terminus (decision 3)
 * @property {string} [linker]         Linker id (default: first library entry)
 * @property {string} [promoter]       Promoter id (default: first library entry)
 */

/** Build one Level 0 part and attach its fixed Type overhangs. */
function level0Part(slot, { role, label, kind, note, bp, surface = false, isCargo = false }) {
  const [overhang5, overhang3] = TYPE_OVERHANGS[slot]
  return { slot, type: `Type ${slot}`, role, label, kind, note, bp, overhang5, overhang3, surface, isCargo }
}

/**
 * Assemble the two Level 1 modules as arrays of 5 Level 0 parts each.
 * The fusion direction decides where the targeting peptide + linker sit
 * relative to the cargo (decision 3 conditions the Level 0 layout).
 */
function buildModules(nc, link, cargoLabel, cargoBp, fusion) {
  const tp = { role: 'targeting-peptide', label: nc.tp, kind: 't1', note: 'Targeting peptide', bp: NOMINAL_BP.TP }
  const lk = { role: 'linker', label: link.label, kind: 't2', note: `${link.aa} aa`, bp: link.bp }
  const cg = { role: 'cargo', label: cargoLabel, kind: 't3', note: `${cargoBp} bp`, bp: cargoBp, isCargo: true }
  const ncs = () => ({ role: 'ncs', label: 'NCS', kind: 'ncs', note: 'Spacer', bp: NOMINAL_BP.NCS })
  // Flanking NC slots are open surface positions (e.g. SpyCatcher on the shell exterior).
  const surf = (label = 'NCS') => ({ role: 'surface', label, kind: 'ncs', note: 'open · e.g. SpyCatcher', bp: NOMINAL_BP.NCS, surface: true })

  // Cargo module — 5 slots. C-terminal: TP·linker·cargo·NCS·NCS.
  //                          N-terminal: NCS·NCS·cargo·linker·TP.
  const cargoLayout = fusion === 'C' ? [tp, lk, cg, ncs(), ncs()] : [ncs(), ncs(), cg, lk, tp]
  const cargoModule = cargoLayout.map((spec, i) => level0Part(i + 1, spec))

  // NC module — shell in the centre, flanked by four open surface slots.
  const ncLayout = [surf(), surf(), { role: 'shell', label: nc.shell, kind: 'shell', note: `${nc.shellBp} bp`, bp: nc.shellBp }, surf('NCS*'), surf()]
  const ncModule = ncLayout.map((spec, i) => level0Part(i + 1, spec))

  return { cargoModule, ncModule }
}

/**
 * Design a cargo primer pair: BsaI site + Golden Gate overhang + annealing
 * region, with the annealing length balanced so the two Tm's are within 5 °C
 * (Wallace rule). Faithful port of the prototype `makePrimerPair`.
 */
export function makePrimerPair(seq, ohF, ohR) {
  let lenF = 22
  let lenR = 22
  for (let i = 0; i < 12; i++) {
    const tmF = wallaceTm(seq.slice(0, lenF))
    const tmR = wallaceTm(reverseComplement(seq.slice(-lenR)))
    if (Math.abs(tmF - tmR) <= 5) break
    if (tmF > tmR && lenF > 16) lenF--
    else if (tmR > tmF && lenR > 16) lenR--
    else break
  }
  const annealF = seq.slice(0, lenF)
  const annealR = reverseComplement(seq.slice(-lenR))
  const build = (oh, anneal) => `${BSAI_PRIMER_PREFIX}${oh}${anneal}`
  return [
    { name: 'Cargo_F', role: 'forward', overhang: ohF, anneal: annealF, full: build(ohF, annealF), length: build(ohF, annealF).length, tm: wallaceTm(annealF) },
    { name: 'Cargo_R', role: 'reverse', overhang: ohR, anneal: annealR, full: build(ohR, annealR), length: build(ohR, annealR).length, tm: wallaceTm(annealR) },
  ]
}

/** 96-well pick plan: which stock wells feed this construct's assembly. */
function buildPlatePlan(nc, link, cargoLabel) {
  return [
    { well: 'A1', kind: 't1', name: nc.tp, tip: nc.tp },
    { well: 'A2', kind: 't2', name: link.label, tip: 'L' },
    { well: 'A3', kind: 't3', name: cargoLabel, tip: 'C' },
    { well: 'B1', kind: 'shell', name: nc.shell, tip: 'Sh' },
    { well: 'B2', kind: 'promo', name: 'GAL1-10', tip: 'P' },
    { well: 'C1', kind: 'ncs', name: 'NCS', tip: 'N' },
    { well: 'C2', kind: 'ncs', name: 'NCS', tip: 'N' },
  ]
}

/** Order list: fixed standard modules + the single new cargo part. */
function buildOrderList(nc, link, cargoModule, cargoLabel, cargoBp, cargoSeq) {
  const roleType = (role) => (cargoModule.find((p) => p.role === role) || {}).type || null
  return {
    fixed: [
      { name: `Targeting peptide ${nc.tp}`, sub: `${roleType('targeting-peptide') || 'Type 1/5'} · standard module`, kind: 't1' },
      { name: `Linker ${link.label}`, sub: `${roleType('linker') || 'Type 2/4'} · standard module`, kind: 't2' },
      { name: `Shell CDS ${nc.shell}`, sub: 'Nanocompartment · standard module', kind: 'shell' },
      { name: 'Promoter GAL1-10', sub: 'bidirectional · standard module', kind: 'promo' },
      { name: 'NCS / surface slot', sub: 'Spacer or display marker (e.g. SpyCatcher)', kind: 'ncs' },
    ],
    new: {
      name: `${cargoLabel} (${cargoBp} bp)`,
      sub: 'Type 3 · your new cargo — synthesis/PCR with overhangs',
      kind: 't3',
      cargoWithOverhangs: `${CARGO_L1_FLANK[0]}${cargoSeq}${CARGO_L1_FLANK[1]}`,
      overhangs: { left: CARGO_L1_FLANK[0], right: CARGO_L1_FLANK[1] },
    },
  }
}

/**
 * Run the full Golden Gate design.
 *
 * @param {Decisions} decisions
 * @returns {Object} A structured design (see fields below). Throws a plain
 *   Error with a `.status` of 400 for invalid input (nanocompartment unknown or
 *   cargo not fusion-ready) so the API layer can translate it to an HTTP 400.
 */
export function designConstruct(decisions = {}) {
  const nc = findNanocompartment(decisions.nanocompartment)
  if (!nc) throw badRequest(`Unknown nanocompartment "${decisions.nanocompartment}".`)

  const fusion = decisions.fusion === 'N' ? 'N' : 'C'
  const link = findLinker(decisions.linker) || LINKERS[0]
  const promoterEntry = findPromoter(decisions.promoter) || findPromoter('GAL110')

  const cargo = validateCargo(decisions.cargoSeq)
  if (!cargo.ok) throw badRequest('Cargo sequence is not fusion-ready.', { cargo })

  const cargoLabel = (decisions.cargoLabel || '').trim() || 'Custom cargo'
  const cargoBp = cargo.length

  const { cargoModule, ncModule } = buildModules(nc, link, cargoLabel, cargoBp, fusion)
  const primers = makePrimerPair(cargo.clean, CARGO_L1_FLANK[0], CARGO_L1_FLANK[1])

  return {
    input: { nanocompartment: nc.id, fusion, linker: link.id, promoter: promoterEntry.id, cargoLabel },
    // decision 1 -> the targeting peptide is fixed by the nanocompartment choice
    nanocompartment: { id: nc.id, label: nc.label, T: nc.T, dia: nc.dia, shell: nc.shell, shellBp: nc.shellBp },
    targetingPeptide: nc.tp,
    linker: { id: link.id, label: link.label, aa: link.aa, bp: link.bp },
    cargo: { label: cargoLabel, sequence: cargo.clean, bp: cargoBp, aa: cargo.aa, gc: cargo.gc, validation: cargo },
    fusion,

    // Level 0 — 10 individual parts (grouped so the module membership is explicit)
    level0: {
      total: cargoModule.length + ncModule.length,
      cargoModule,
      ncModule,
    },

    // Level 1 — 2 assembled modules with their fuse-to-Level-2 flanks
    level1: {
      cargoModule: { role: `${fusion}-terminal cargo module`, enzyme: 'BsaI', flanks: { left: CARGO_L1_FLANK[0], right: CARGO_L1_FLANK[1] }, parts: cargoModule },
      ncModule: { role: 'nanocompartment module', enzyme: 'BsaI', flanks: { left: NC_L1_FLANK[0], right: NC_L1_FLANK[1] }, parts: ncModule },
    },

    // Level 2 — bidirectional construct: cargo module <- promoter -> NC module
    level2: {
      promoter: { id: promoterEntry.id, label: promoterEntry.label, kind: 'promo', bp: NOMINAL_BP.PROMO, flanks: { left: PROMO_FLANK[0], right: PROMO_FLANK[1] } },
      totalLevel0: cargoModule.length + ncModule.length, // 10
      layout: {
        left: { module: 'cargoModule', strand: 'antisense (−)', direction: "3' ◄ 5'" },
        centre: { module: 'promoter', label: promoterEntry.label },
        right: { module: 'ncModule', strand: 'sense (+)', direction: "5' ► 3'" },
      },
    },

    primers,
    platePlan: buildPlatePlan(nc, link, cargoLabel),
    orderList: buildOrderList(nc, link, cargoModule, cargoLabel, cargoBp, cargo.clean),
    warnings: cargo.warnings,
  }
}

/* ------------------------------------------------------------------ *
 * FASTA export (prototype: standard parts are deterministic placeholder
 * sequences; only the cargo is the user's real input). Kept in the engine so
 * the export matches whatever the design produced. Replace the placeholders
 * with real toolbox sequences from the DB — see PROJECT_TODO.txt.
 * ------------------------------------------------------------------ */

/** Deterministic pseudo-random A/T/G/C sequence of fixed length (mock only). */
function placeholderSeq(seed, len) {
  const bases = 'ATGC'
  let x = 0
  for (const c of seed) x = (x * 31 + c.charCodeAt(0)) >>> 0
  let s = ''
  for (let i = 0; i < len; i++) {
    x = (x * 1103515245 + 12345) >>> 0
    s += bases[(x >>> 16) % 4]
  }
  return s
}

const fastaWrap = (seq, width = 70) => {
  const lines = []
  for (let i = 0; i < seq.length; i += width) lines.push(seq.slice(i, i + width))
  return lines.join('\n')
}

/**
 * Build a multi-record FASTA string for a design produced by designConstruct().
 * @param {ReturnType<typeof designConstruct>} design
 * @returns {string}
 */
export function buildFasta(design) {
  const out = []
  const add = (header, seq) => out.push(`>${header}\n${fastaWrap(seq)}`)

  const nc = design.nanocompartment
  const link = design.linker
  const cargoSeq = design.cargo.sequence
  const cargoName = design.cargo.label.replace(/\s+/g, '-')

  const tpSeq = placeholderSeq('TP' + design.targetingPeptide, 36)
  const linkSeq = placeholderSeq('LINK' + link.id, link.bp)
  const shellSeq = placeholderSeq('SHELL' + nc.shell, nc.shellBp)
  const promoSeq = placeholderSeq('PROMO' + design.level2.promoter.id, 600)
  const ncsSeq = placeholderSeq('NCS', 30)

  add(`Targeting-Peptide_${design.targetingPeptide} [Type1/5] [PLACEHOLDER]`, tpSeq)
  add(`Linker_${link.id} [Type2/4] [PLACEHOLDER]`, linkSeq)
  add(`Cargo_${cargoName} [Type3] [REAL INPUT ${cargoSeq.length}bp]`, cargoSeq)
  add(`Nanocompartment-Shell_${nc.shell} [PLACEHOLDER]`, shellSeq)
  add(`Promoter_${design.level2.promoter.label} [bidirectional] [PLACEHOLDER]`, promoSeq)
  add(`NCS-Spacer [PLACEHOLDER]`, ncsSeq)
  add(`Cargo_${cargoName}_with-overhangs`, `${CARGO_L1_FLANK[0]}${cargoSeq}${CARGO_L1_FLANK[1]}`)

  const cargoModuleSeq =
    design.fusion === 'C'
      ? tpSeq + linkSeq + cargoSeq + ncsSeq + ncsSeq
      : ncsSeq + ncsSeq + cargoSeq + linkSeq + tpSeq
  const ncModuleSeq = ncsSeq + ncsSeq + shellSeq + ncsSeq + ncsSeq
  add(`Level1_Cargo-Module_${design.fusion}-terminal [${design.cargo.label}]`, cargoModuleSeq)
  add(`Level1_Nanocompartment-Module [${nc.shell}]`, ncModuleSeq)

  const level2 = reverseComplement(cargoModuleSeq) + promoSeq + ncModuleSeq
  add(`Level2_pESC-ENCORE-${nc.id}_COMPLETE [~${level2.length}bp] [Cargo(rev)<-promoter->NC]`, level2)

  const banner =
    '; ENCORE Builder — FASTA export (prototype)\n' +
    '; Standard modules are PLACEHOLDER sequences; only the cargo is real input.\n'
  return banner + out.join('\n')
}

/* ------------------------------------------------------------------ */

/** Build a 400-style error the API layer can recognise. */
function badRequest(message, data) {
  const err = new Error(message)
  err.status = 400
  if (data) err.data = data
  return err
}
