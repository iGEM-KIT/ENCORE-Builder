#!/usr/bin/env python3
"""Convert the curated Open Encapsulin Databank Excel workbook to Selector JSON.

Python standard library only (no pip packages). The workbook is READ-ONLY.

Modes:
  python scripts/export-excel-to-json.py --check
  python scripts/export-excel-to-json.py --write

--check: validates Excel and compares exported records to existing JSON; changes nothing.
         Exit 0 when in sync, 1 when out of sync, 2 on validation/IO errors.
--write: validates everything first, then writes changed/new JSON files atomically.
         Unexpected old IDs are never deleted automatically: --write stops instead.

This script deliberately does not modify build-selector-data.mjs, selector-data.js,
Selector UI files, or the Excel. The generated pore/evidence/citation JSON will be
integrated into build-selector-data.mjs in a separate, tested change.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "encapsulin_selector" / "data"
DEFAULT_XLSX = DATA_DIR / "Open_Encapsulin_Databank.xlsx"
NS = {
    "x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "p": "http://schemas.openxmlformats.org/package/2006/relationships",
}
DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", flags=re.IGNORECASE)
DNA_RE = re.compile(r"^[ACGTRYSWKMBDHVN]*$")  # IUPAC DNA ambiguity symbols

# These are *data* worksheets. README is documentation; the T-column
# legacy_review_note_not_for_export is never imported into assemblies JSON.
TABLES = {
    "databank": ("candidate_id", "candidates"),
    "assemblies": ("assembly_id", "assemblies"),
    "sequence_links": ("sequence_link_id", "sequences"),
    "pores": ("pore_record_id", "pores"),
    "evidence": ("evidence_id", "evidence"),
}
LIST_TABLES = {
    "doi_index": "doi_index.json",
    "citation_links": "citation_links.json",
    # Keep public TP records and pair-specific evidence in separate JSON lists.
    "targeting_peptides": "targeting_peptides.json",
    "tp_assembly_links": "tp_assembly_links.json",
}

# Fields with specific types in the public JSON, not default text.
INT_FIELDS = {
    "taxonomy_id", "length_aa", "pdb_count", "assembly_count", "pore_record_count",
    "evidence_record_count", "T_number", "shell_subunit_count", "tp_length_aa", "cds_start",
    "cds_end", "cds_length_nt", "linked_record_count", "protein_length_aa",
}
BOOLEAN_FIELDS = {"needs_review_flag", "used_in_databank"}
FLOAT_FIELDS = {"pore_diameter_nm", "pH", "value_numeric"}
# Only these columns can be interpreted as numbers when the cell contains
# a *single* number. A range or an approximation stays as text.
MEASURE_FIELDS = {
    "shell_diameter_nm", "inner_diameter_nm", "wall_thickness_nm",
    "inner_volume_A3", "thermostability_tm_c",
}


class ExportError(Exception):
    pass


def column_index(ref: str) -> int:
    letters = re.match(r"[A-Z]+", ref)
    if not letters:
        raise ExportError(f"Invalid Excel cell coordinate: {ref!r}")
    out = 0
    for char in letters.group():
        out = 26 * out + ord(char) - ord("A") + 1
    return out - 1


def find_xml_target(target: str) -> str:
    """Resolve workbook relationship targets without accessing outside xl/."""
    from posixpath import normpath
    result = normpath(target.lstrip("/") if target.startswith("/") else "xl/" + target)
    if not result.startswith("xl/") or ".." in result.split("/"):
        raise ExportError(f"Unexpected worksheet location: {target}")
    return result


def read_xlsx(path: Path) -> dict[str, list[dict]]:
    """Read only actual populated cells using XLSX's XML parts (no Excel rewrite).

    This intentionally ignores Excel formatting, phantom million-row ranges,
    and formula text. For formulas it uses the last stored/cached value, with
    deterministic reconstructions for the five known derived column types.
    """
    if not path.is_file():
        raise ExportError(f"Workbook not found: {path}")
    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ExportError(f"Cannot open .xlsx: {exc}") from exc
    with archive as z:
        try:
            book = ET.fromstring(z.read("xl/workbook.xml"))
            rel_root = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        except (KeyError, ET.ParseError) as exc:
            raise ExportError(f"Not a valid unencrypted XLSX file: {exc}") from exc
        rel = {e.attrib["Id"]: e.attrib["Target"] for e in rel_root}
        strings = []
        if "xl/sharedStrings.xml" in z.namelist():
            xml = ET.fromstring(z.read("xl/sharedStrings.xml"))
            strings = ["".join(t.text or "" for t in si.findall(".//x:t", NS))
                       for si in xml.findall("x:si", NS)]

        def cell_value(cell: ET.Element):
            kind = cell.attrib.get("t", "n")
            if kind == "inlineStr":
                return "".join(t.text or "" for t in cell.findall(".//x:t", NS))
            el = cell.find("x:v", NS)
            if el is None or el.text is None:
                return None
            raw = el.text
            if kind == "s":
                try:
                    return strings[int(raw)]
                except (ValueError, IndexError) as exc:
                    raise ExportError(f"Broken shared string index: {raw}") from exc
            if kind == "b":
                return raw == "1"
            if kind == "e":
                raise ExportError(f"Excel cell error at {cell.attrib.get('r')}: {raw}")
            if kind in ("str", "d"):
                return raw
            try:
                num = float(raw)
                return int(num) if num.is_integer() else num
            except ValueError:
                return raw

        tables = {}
        for item in book.findall("x:sheets/x:sheet", NS):
            sheet_name = item.attrib["name"]
            if sheet_name not in (*TABLES.keys(), *LIST_TABLES.keys(), "vocabularies", "builder_catalog"):
                continue
            worksheet_target = find_xml_target(rel[item.attrib["{%s}id" % NS["r"]]])
            try:
                root = ET.fromstring(z.read(worksheet_target))
            except KeyError as exc:
                raise ExportError(f"Missing worksheet XML for {sheet_name}: {worksheet_target}") from exc
            rows = []
            for row in root.findall("x:sheetData/x:row", NS):
                cells = {}
                for cell in row.findall("x:c", NS):
                    value = cell_value(cell)
                    if value is not None and value != "":
                        cells[column_index(cell.attrib["r"])] = value
                if cells:
                    rows.append((int(row.attrib["r"]), cells))
            if not rows or rows[0][0] != 1:
                raise ExportError(f"{sheet_name}: missing first-row headers")
            _, header_cells = rows[0]
            headers = {col: str(value).strip() for col, value in header_cells.items()}
            if len(set(headers.values())) != len(headers):
                raise ExportError(f"{sheet_name}: duplicate column names")
            items = []
            for rownum, cells in rows[1:]:
                record = {header: cells.get(column) for column, header in headers.items()}
                record["__excel_row"] = rownum  # Validation context only; never exported.
                items.append(record)
            tables[sheet_name] = items
        return tables


def is_missing(x) -> bool:
    return x is None or (isinstance(x, str) and not x.strip())


def cast_cell(value, field, context):
    if is_missing(value):
        return None
    if isinstance(value, str):
        value = value.strip()  # Excel line wraps inside notes stay intact.
    if field in BOOLEAN_FIELDS:
        if isinstance(value, bool):
            return value
        if str(value).lower() in ("true", "1", "yes"):
            return True
        if str(value).lower() in ("false", "0", "no"):
            return False
        raise ExportError(f"{context}: invalid Boolean for {field}: {value!r}")
    if field in INT_FIELDS:
        try:
            v = float(value)
            if not v.is_integer():
                raise ValueError("not an integer")
            return int(v)
        except (ValueError, TypeError) as exc:
            raise ExportError(f"{context}: invalid integer {field}={value!r}") from exc
    if field in FLOAT_FIELDS:
        try:
            return float(value)
        except (ValueError, TypeError) as exc:
            raise ExportError(f"{context}: invalid numeric {field}={value!r}") from exc
    if field in MEASURE_FIELDS:
        if isinstance(value, (int, float)):
            return value
        # Preserve scientifically meaningful ~, ranges, scientific notation
        # (including strings like '3.09 × 106') rather than guessing numbers.
        if re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", str(value)):
            return float(value) if "." in str(value) else int(value)
        return str(value)
    if field in ("charge_exterior", "charge_interior") and isinstance(value, str) and value.upper() == "LOOK AT FIGURE 3":
        # Unresolved editorial placeholders are NOT valid scientific charges.
        # Leave the Excel intact and export null until the curator decides.
        return None
    if field == "genomic_sequence":
        seq = re.sub(r"\s+", "", str(value)).upper()
        if seq and not DNA_RE.fullmatch(seq):
            raise ExportError(f"{context}: invalid nucleotide characters in genomic_sequence")
        return seq or None
    return value


def tidy(records: list[dict], sheet: str, id_column: str | None = None) -> list[dict]:
    output = []
    for row in records:
        excel_row = row["__excel_row"]
        if id_column is not None and is_missing(row.get(id_column)):
            # This is expected for the TOTAL_CDS_LENGTH row in sequence_links,
            # or commentary below the data tables. Never export it as a record.
            continue
        if sheet == "assemblies":
            row = {k: v for k, v in row.items() if k != "legacy_review_note_not_for_export"}
        if sheet == "databank":
            # Derived dynamically from JSON by build-selector-data.mjs.
            # Retain the Excel formula, not an out-of-date JSON duplicate.
            row = {k: v for k, v in row.items() if k != "assembly_count"}
        if sheet == "sequence_links" and is_missing(row.get("sequence_link_id")):
            continue
        out = {}
        for k, v in row.items():
            if k.startswith("__"):
                continue
            out[k] = cast_cell(v, k, f"{sheet}!row {excel_row}")
        if sheet == "sequence_links":
            # If Excel did not save a cached formula result for CDS length,
            # derive it only from explicit CDS coordinates, never from a guess.
            if out.get("cds_length_nt") is None:
                a, b = out.get("cds_start"), out.get("cds_end")
                out["cds_length_nt"] = abs(b - a) + 1 if a is not None and b is not None else 0
        output.append(out)
    return output


def make_export(tables: dict[str, list[dict]]):
    needed = set(TABLES) | set(LIST_TABLES) | {"vocabularies"}
    missing = sorted(needed - tables.keys())
    if missing:
        raise ExportError("Workbook missing sheet(s): " + ", ".join(missing))
    for name, (key, _) in TABLES.items():
        headers = set(tables[name][0]) if tables[name] else set()
        if key not in headers:
            raise ExportError(f"Missing {key} column in {name}")

    sources = {}
    for name, (id_col, _) in TABLES.items():
        sources[name] = tidy(tables[name], name, id_col)
    for name in LIST_TABLES:
        sources[name] = tidy(tables[name], name)

    vocab = collections.OrderedDict()
    for row in tables["vocabularies"]:
        for key, value in row.items():
            if key.startswith("__") or is_missing(value):
                continue
            vocab.setdefault(key, [])
            casted = cast_cell(value, key, f"vocabularies!row {row['__excel_row']}")
            if casted not in vocab[key]:
                vocab[key].append(casted)
    sources["vocabularies"] = dict(vocab)

    # The reviewed CDS catalog is a separate, strict 24-row view of the same
    # workbook. Never infer additional Builder-eligible sequences from DNA availability.
    catalog = []
    for row in tables.get("builder_catalog", []):
        if is_missing(row.get("sequence_id")):
            continue
        mapping = {
            "shell_name": "name", "organism": "organism", "candidate_id": "candidate_id",
            "assembly_id": "assembly_id", "sequence_id": "sequence_id",
            "protein_length_aa": "protein_length_aa", "cds_length_nt": "cds_length_nt",
            "translation_qc": "translation_qc", "coding_DNA_5to3": "cds",
            "protein_variant_id": "protein_variant_id",
        }
        output = {target:cast_cell(row.get(source),target,"builder_catalog") for source,target in mapping.items()}
        catalog.append(output)
    sources["builder_catalog"] = catalog

    # Derived formula results in XLSX may lack cached <v> values if the
    # workbook was last saved by a library rather than Excel itself.
    # Recover only counts that can be calculated exactly from data here.
    pores_per = collections.Counter(r["candidate_id"] for r in sources["pores"])
    evidence_per = collections.Counter(r["candidate_id"] for r in sources["evidence"])
    for candidate in sources["databank"]:
        cid = candidate["candidate_id"]
        if candidate.get("pore_record_count") is None:
            candidate["pore_record_count"] = pores_per[cid]
        if candidate.get("evidence_record_count") is None:
            candidate["evidence_record_count"] = evidence_per[cid]
        if candidate.get("pdb_count") is None and candidate.get("source_pdb"):
            candidate["pdb_count"] = len([x for x in candidate["source_pdb"].split(";") if x.strip()])
    if len(sources["builder_catalog"]) != 24:
        raise ExportError(f"builder_catalog must contain exactly 24 approved designs, found {len(sources['builder_catalog'])}")
    catalog_ids=set()
    assembly_candidates = {r["assembly_id"]:r["candidate_id"] for r in sources["assemblies"]}
    for c in sources["builder_catalog"]:
        if c["sequence_id"] in catalog_ids:
            raise ExportError(f"builder_catalog: duplicate sequence ID {c['sequence_id']}")
        catalog_ids.add(c["sequence_id"])
        if c["translation_qc"] != "PASS" or assembly_candidates.get(c["assembly_id"]) != c["candidate_id"]:
            raise ExportError(f"builder_catalog: not approved or unknown assembly for {c['sequence_id']}")
        cds = c["cds"]
        if not isinstance(cds,str) or not re.fullmatch(r"[ACGT]+",cds) or len(cds) != c["cds_length_nt"] or len(cds)%3:
            raise ExportError(f"builder_catalog: invalid CDS/length {c['sequence_id']}")
    return sources


def split_dois(value):
    if is_missing(value):
        return []
    return [d.strip() for d in str(value).split(";") if d.strip()]


def validate(data: dict) -> list[str]:
    """Validate referential integrity before even showing a write option."""
    errors = []
    uniques = {}
    for sheet, (key, _) in TABLES.items():
        uniques[sheet] = {}
        for row in data[sheet]:
            item = row.get(key)
            if not isinstance(item, str) or not item.strip():
                errors.append(f"{sheet}: missing {key}")
                continue
            if item != item.strip():
                errors.append(f"{sheet}: whitespace in {key}={item!r}")
            if item in uniques[sheet]:
                errors.append(f"{sheet}: duplicate {key}: {item}")
            uniques[sheet][item] = row
    candidates = uniques["databank"]
    assemblies = uniques["assemblies"]
    for sheet in ("assemblies", "sequence_links", "pores", "evidence", "targeting_peptides"):
        for row in data[sheet]:
            if row.get("candidate_id") not in candidates:
                errors.append(f"{sheet}: missing candidate {row.get('candidate_id')!r}")

    # Public release TP records are not necessarily validated for every shell.
    # Validate their identity and sequences without upgrading evidence status.
    tps = {}
    for tp in data["targeting_peptides"]:
        tp_id = tp.get("tp_id")
        if not isinstance(tp_id, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", tp_id):
            errors.append(f"targeting_peptides: invalid tp_id {tp_id!r}")
            continue
        if tp_id in tps:
            errors.append(f"targeting_peptides: duplicate tp_id {tp_id}")
        tps[tp_id] = tp
        sequence = tp.get("tp_sequence_aa")
        if not isinstance(sequence, str) or not re.fullmatch(r"[ACDEFGHIKLMNPQRSTVWY]+", sequence):
            errors.append(f"targeting_peptides: invalid protein sequence {tp_id}")
        elif len(sequence) != tp.get("tp_length_aa"):
            errors.append(f"targeting_peptides: length mismatch {tp_id}")
        motif = tp.get("tp_core_motif_aa")
        if motif and isinstance(sequence, str) and motif not in sequence:
            errors.append(f"targeting_peptides: motif not found in sequence {tp_id}")
        dna = tp.get("builder_dna_5to3")
        if dna and (not isinstance(dna, str) or not re.fullmatch(r"[ACGT]+", dna) or len(dna) % 3):
            errors.append(f"targeting_peptides: invalid Builder DNA {tp_id}")

    # Check 50 specific shell-design/TP associations, not mere candidate matches.
    catalog = {r["sequence_id"]: r for r in data["builder_catalog"]}
    pair_ids, pairs, covered = set(), set(), set()
    for link in data["tp_assembly_links"]:
        lid = link.get("tp_assembly_link_id")
        sid = link.get("sequence_id")
        aid = link.get("assembly_id")
        cid = link.get("candidate_id")
        tid = link.get("tp_id")
        if not lid or lid in pair_ids:
            errors.append(f"tp_assembly_links: duplicate or missing link ID {lid!r}")
        pair_ids.add(lid)
        if (sid, tid) in pairs:
            errors.append(f"tp_assembly_links: duplicate design/TP pair {sid}/{tid}")
        pairs.add((sid, tid))
        design = catalog.get(sid)
        if design is None or design["assembly_id"] != aid or design["candidate_id"] != cid:
            errors.append(f"tp_assembly_links: invalid Builder design {lid}: {sid}/{aid}/{cid}")
        else:
            covered.add(sid)
        tp = tps.get(tid)
        if tp is None or tp["candidate_id"] != cid:
            errors.append(f"tp_assembly_links: invalid TP {lid}: {tid}/{cid}")
    if len(tps) != 19 or len(data["tp_assembly_links"]) != 50:
        errors.append("TP release count mismatch: expected 19 TPs and 50 assembly links")
    if covered != set(catalog):
        errors.append(f"tp_assembly_links: only {len(covered)}/24 Builder designs covered")
    uniques["targeting_peptides"] = tps
    for row in data["databank"]:
        ref = row.get("reference_assembly_id")
        if ref and (ref not in assemblies or assemblies[ref].get("candidate_id") != row["candidate_id"]):
            errors.append(f"databank: invalid reference_assembly_id {ref} for {row['candidate_id']}")
    for row in data["pores"]:
        aid = row.get("assembly_id")
        if aid not in assemblies:
            errors.append(f"pores: missing assembly {aid!r} for {row['pore_record_id']}")
        elif assemblies[aid]["candidate_id"] != row["candidate_id"]:
            errors.append(f"pores: {row['pore_record_id']} candidate differs from assembly {aid}")
    for seq in data["sequence_links"]:
        letters = seq.get("genomic_sequence")
        if letters and seq.get("cds_length_nt") not in (None, 0, len(letters)):
            errors.append(f"sequence_links: {seq['sequence_link_id']} CDS length {seq['cds_length_nt']} != sequence length {len(letters)}")
        if letters is None and seq.get("cds_length_nt") not in (None, 0):
            # Coordinates can still be known without having extracted the sequence.
            pass
    index = {}
    for row in data["doi_index"]:
        doi = row.get("doi")
        if is_missing(doi):
            continue
        if not isinstance(doi, str) or not DOI_RE.match(doi):
            errors.append(f"doi_index: invalid DOI {doi!r}")
        if doi.lower() in index:
            errors.append(f"doi_index: duplicate DOI {doi}")
        index[doi.lower()] = row
    keys = {"databank": "candidate_id", "assemblies": "assembly_id",
            "pores": "pore_record_id", "targeting_peptides": "tp_id"}
    for row in data["citation_links"]:
        doi = row.get("doi")
        table = row.get("table")
        record_id = row.get("record_id")
        if not doi or doi.lower() not in index:
            errors.append(f"citation_links: {table}/{record_id} references unknown DOI {doi}")
        if table not in keys:
            errors.append(f"citation_links: unknown table {table}")
        elif record_id not in uniques[table]:
            errors.append(f"citation_links: unknown {table} record {record_id}")
        elif uniques[table][record_id]["candidate_id"] != row.get("candidate_id"):
            errors.append(f"citation_links: candidate mismatch for {table}/{record_id}")
    # A DOI in source_doi should be in doi_index; we cannot reliably guess its
    # bibliography if absent, so fail rather than silently exporting orphan DOIs.
    for sheet in ("databank", "assemblies", "pores", "evidence", "targeting_peptides"):
        field = "curation_source_doi" if sheet == "databank" else "source_doi"
        for row in data[sheet]:
            for doi in split_dois(row.get(field)):
                if not DOI_RE.match(doi):
                    errors.append(f"{sheet}: invalid DOI {doi!r}")
                elif doi.lower() not in index:
                    errors.append(f"{sheet}: DOI {doi} absent from doi_index")
    return errors


def export_warnings(tables: dict, data: dict) -> list[str]:
    issues = []
    for row in tables["pores"]:
        for field in ("charge_exterior", "charge_interior"):
            if str(row.get(field, "")).strip().upper() == "LOOK AT FIGURE 3":
                issues.append(f"pores row {row['__excel_row']} {field}: unresolved editor note exported as null (Excel unchanged)")
    for c in data["databank"]:
        src = c.get("source_pdb") or ""
        count = len([x for x in re.split(r"[;,]", src) if x.strip()])
        if src and c.get("pdb_count") not in (None, count):
            issues.append(f"{c['candidate_id']}: pdb_count={c['pdb_count']} but {count} nonblank PDB identifiers; correct Excel formula/source")
    return issues


def output_targets(data: dict):
    # Each target path is relative to data/. Filenames come only from IDs
    # but must be checked to avoid unsafe filenames/path traversal.
    targets = {}
    for name, (key, folder) in TABLES.items():
        for row in data[name]:
            ident = row[key]
            if not re.fullmatch(r"[A-Za-z0-9_.-]+", ident) or ident.startswith("."):
                raise ExportError(f"Unsafe {key} for filename: {ident!r}")
            targets[f"{folder}/{ident}.json"] = row
    for name, filename in LIST_TABLES.items():
        targets[filename] = data[name]
    targets["vocabularies.json"] = data["vocabularies"]
    targets["builder_catalog.json"] = data["builder_catalog"]
    return targets


def brief_diff(previous, updated, *, limit=9):
    if not isinstance(previous, dict) or not isinstance(updated, dict):
        return ["record content changed"]
    keys = sorted(set(previous) | set(updated))
    diff = [key for key in keys if previous.get(key) != updated.get(key)]
    return diff[:limit] + ([f"... +{len(diff)-limit} more"] if len(diff) > limit else [])


def compare(targets, directory: Path):
    added, changed, unchanged, deletions = [], [], [], []
    for relpath, content in targets.items():
        path = directory / relpath
        if not path.exists():
            added.append(relpath)
            continue
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeError, OSError, json.JSONDecodeError) as exc:
            raise ExportError(f"Existing JSON is unreadable: {path}: {exc}") from exc
        if old == content:
            unchanged.append(relpath)
        else:
            changed.append((relpath, brief_diff(old, content)))
    # Existing IDs absent from the spreadsheet are never silently deleted.
    for sheet, (_, folder) in TABLES.items():
        subdir = directory / folder
        if not subdir.is_dir():
            continue
        for file in subdir.glob("*.json"):
            if file.name.startswith("_"):
                continue
            rel = f"{folder}/{file.name}"
            if rel not in targets:
                deletions.append(rel)
    return added, changed, unchanged, deletions


def atomic_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    contents = json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    # Same-directory temp + atomic replace; do not partially corrupt JSON.
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=".excel-export-", suffix=".tmp", delete=False) as fp:
        tmp = Path(fp.name)
        fp.write(contents)
    try:
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Read/validate/compare only; never writes")
    mode.add_argument("--write", action="store_true", help="Write changed/new JSON after validation")
    parser.add_argument("--excel", type=Path, default=DEFAULT_XLSX, help="Path to the final XLSX")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR,
                        help="Target folder (default: encapsulin_selector/data)")
    parser.add_argument("--show", type=int, default=12,
                        help="Maximum changed records to print (default: 12)")
    args = parser.parse_args()
    try:
        excel_tables = read_xlsx(args.excel)
        data = make_export(excel_tables)
        errors = validate(data)
        if errors:
            print(f"ERROR: {len(errors)} scientific/data-integrity problem(s):", file=sys.stderr)
            for msg in errors[:35]:
                print("  - " + msg, file=sys.stderr)
            if len(errors) > 35:
                print(f"  ... +{len(errors)-35} more", file=sys.stderr)
            return 2
        warnings = export_warnings(excel_tables, data)
        if warnings:
            print(f"Warning: {len(warnings)} issue(s) needing manual review (not changed):")
            for msg in warnings[:20]:
                print("  ! " + msg)
        targets = output_targets(data)
        added, changed, unchanged, deletions = compare(targets, args.data_dir)
        print("Validated:", ", ".join(f"{sheet}={len(data[sheet])}" for sheet in TABLES))
        print(f"  doi_index={len(data['doi_index'])}, citation_links={len(data['citation_links'])}, approved_builder_sequences={len(data['builder_catalog'])}")
        print(f"  targeting_peptides={len(data['targeting_peptides'])}, tp_assembly_links={len(data['tp_assembly_links'])}")
        print(f"  genomic sequences available={sum(bool(x.get('genomic_sequence')) for x in data['sequence_links'])}")
        print(f"Compared: {len(added)} new, {len(changed)} different, {len(unchanged)} unchanged, {len(deletions)} unexpected old files")
        for rel in added[:args.show]:
            print("  + " + rel)
        for rel, fields in changed[:args.show]:
            print("  ~ " + rel + " | fields: " + ", ".join(fields))
        if len(added) > args.show or len(changed) > args.show:
            print("  ... output shortened (--show to adjust)")
        if deletions:
            print("STOP: existing JSON IDs missing from Excel:", file=sys.stderr)
            for rel in deletions[:20]:
                print("  - " + rel, file=sys.stderr)
            print("Resolve manually; no files will be deleted automatically.", file=sys.stderr)
            return 2
        if args.check:
            print("CHECK ONLY: no files changed.")
            return 1 if added or changed else 0
        for rel in added + [r for r, _ in changed]:
            atomic_json(args.data_dir / rel, targets[rel])
        print(f"WRITE COMPLETE: {len(added)+len(changed)} JSON files created/updated. Excel untouched.")
        print("Next step: run node scripts/build-selector-data.mjs to refresh the browser data files.")
        return 0
    except (ExportError, OSError, ET.ParseError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
