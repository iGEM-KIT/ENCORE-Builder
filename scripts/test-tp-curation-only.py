#!/usr/bin/env python3
"""Regression check: curated TP sheet exists, but is NOT part of current selector exports.

Stdlib only; does not modify any file.
"""
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
from zipfile import ZipFile

root=Path(__file__).resolve().parents[1]
xl=root/'encapsulin_selector/data/Open_Encapsulin_Databank.xlsx'
ns={'x':'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
    'r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
with ZipFile(xl) as z:
    wb=ET.fromstring(z.read('xl/workbook.xml'))
    names={s.get('name') for s in wb.findall('x:sheets/x:sheet',ns)}
    assert 'targeting_peptides' in names, 'Public workbook is missing TP sheet'
    rels=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
    rid={r.get('Id'):r.get('Target') for r in rels}
    sh=next(s for s in wb.findall('x:sheets/x:sheet',ns) if s.get('name')=='targeting_peptides')
    from posixpath import normpath
    target=rid[sh.get('{%s}id'%ns['r'])]
    sheet_path=normpath(target.lstrip('/') if target.startswith('/') else 'xl/'+target)
    data=ET.fromstring(z.read(sheet_path))
    tp_rows=[r for r in data.findall('x:sheetData/x:row',ns)
             if 2<=int(r.get('r'))<=23 and any(c.get('r')=='A'+r.get('r') for c in r.findall('x:c',ns))]
    assert len(tp_rows)==22, f'Expected 22 TP rows, found {len(tp_rows)}'
    for r in tp_rows:
        n=r.get('r')
        for col in ('X','Y'):
            cell=next((c for c in r.findall('x:c',ns) if c.get('r')==col+n),None)
            assert cell is not None and cell.find('x:f',ns) is not None, f'{col}{n}: missing live Excel formula'

export=(root/'scripts/export-excel-to-json.py').read_text(encoding='utf-8')
# Verify the whitelist, without importing the exporter or changing its logic.
for section in ('TABLES = {','LIST_TABLES = {'):
    assert section in export
assert not re.search(r'^\s*["\']targeting_peptides["\']\s*:',export,re.M), 'TPs unexpectedly configured for export'
cat=(root/'encapsulin_selector/data/builder_catalog.json')
# The Builder catalog may be located only in the Excel, depending on release; no new TP catalog is created.
assert not (root/'encapsulin_selector/data/targeting_peptides.json').exists()
print('PASS: 22 TP records and live verification formulas in public Excel; no TP export registered.')
