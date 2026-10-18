#!/usr/bin/env python3
"""Basic static regression checks for ENCORE Overview and navigation; standard library only."""
from pathlib import Path
import re
root=Path(__file__).resolve().parents[1]
s=(root/'encapsulin_selector'/'overview.html').read_text(encoding='utf-8')
assert s.count('class="term-card"')==20, 'Missing scientific glossary term(s)'
for x in ('T-number','UniProt ID','CDS','Wild Type (WT)','Engineered','Assembly','Pore','DOI / source'):
 assert x in s, f'Missing glossary entry: {x}'
for x in ('id="how-to-use"','id="glossary"','id="sequence-to-shell"','Select for Builder','199–201','KTG','HHH'):
 assert x in s,x
for fname in ('overview.html','builder-filter.html','selector-alpha.html'):
 html=(root/'encapsulin_selector'/fname).read_text(encoding='utf8')
 for url in ('/selector/overview.html','/selector/builder-filter.html','/selector/selector-alpha.html'):
  assert f'href="{url}"' in html,f'{fname} missing {url}'
 assert 'class="databank-nav"' in html
index=(root/'frontend/index.html').read_text(encoding='utf8')
assert 'href="/selector/overview.html">Open NC Databank' in index
assert 'Common questions' not in s
assert 'Welcome to the Open NC Databank' in s
assert 'same WT amino-acid sequence' in s and 'codon optimization' in s
assert 'reported experimental assemblies' in (root/'encapsulin_selector'/'builder-filter.html').read_text(encoding='utf8')
for fname in ('overview.html','builder-filter.html','selector-alpha.html'):
 html=(root/'encapsulin_selector'/fname).read_text(encoding='utf8')
 assert '>ENCORE Builder</a>' in html and '>Open NC Databank</a>' in html, fname
 assert 'OPEN NANOCOMPARTMENTS DATABANK' not in html
print('PASS: Overview glossary, new DNA/protein/assembly explanation, notice, and renamed navigation.')

# Community contributions remain an honest, nonfunctional placeholder until scientific review is implemented.
assert 'id="contribute"' in s
assert 'Help the Open NC Databank grow' in s
assert 'href="#contribute"' in s
assert '<button type="button" disabled' in s
for x in ('New encapsulin', 'Additional assembly', 'Engineered modification', 'Pore or property data', 'Corrections'):
 assert x in s, x
print('PASS: Community contributions section and clearly disabled submission placeholder.')
