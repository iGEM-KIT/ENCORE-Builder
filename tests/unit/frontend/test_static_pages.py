"""Static checks of the pages (frontend/*.html, encapsulin_selector/*): well-formed HTML, working internal links,
every element the script looks up exists, and the house rules for visible text.

The pages are plain HTML with inline scripts and no build step, so these checks are the cheap safety net that a typo in an
id or a broken tag does not reach the user.
"""

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
INDEX = ROOT / "frontend" / "index.html"
GUIDE = ROOT / "frontend" / "guide.html"
SELECTOR_HTML = ROOT / "encapsulin_selector" / "selector-alpha.html"
SELECTOR_JS = ROOT / "encapsulin_selector" / "selector-alpha.js"
PAGES = [INDEX, GUIDE, SELECTOR_HTML]

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


class Structure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.errors, self.ids, self.hrefs = [], [], [], []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.append(attrs["id"])
        if tag == "a" and attrs.get("href"):
            self.hrefs.append(attrs["href"])
        if tag not in VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        else:
            self.errors.append(f"unexpected </{tag}> (open: {self.stack[-3:]})")


def parse(path):
    parser = Structure()
    parser.feed(path.read_text(encoding="utf8"))
    return parser


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
def test_html_tags_are_balanced(page):
    parser = parse(page)
    assert parser.errors == [], parser.errors[:3]
    assert parser.stack == [], f"unclosed tags: {parser.stack}"


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
def test_ids_are_unique(page):
    ids = parse(page).ids
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    assert duplicates == [], f"duplicate ids: {duplicates}"


def test_every_id_the_builder_script_looks_up_exists_in_the_page():
    text = INDEX.read_text(encoding="utf8")
    known = set(re.findall(r'\bid="([A-Za-z0-9_\-]+)"', text)) | set(re.findall(r"\bid=\\?['\"]([A-Za-z0-9_\-]+)", text))
    wanted = set(re.findall(r"\$\('#([A-Za-z0-9_\-]+)'\)", text)) | set(re.findall(r'getElementById\(["\']([A-Za-z0-9_\-]+)["\']\)', text))
    missing = sorted(wanted - known)
    assert missing == [], f"the script looks up ids that are not in the page: {missing}"


def test_every_id_the_selector_script_looks_up_exists_in_the_page():
    html = SELECTOR_HTML.read_text(encoding="utf8")
    js = SELECTOR_JS.read_text(encoding="utf8")
    known = set(re.findall(r'\bid="([A-Za-z0-9_\-]+)"', html)) | set(re.findall(r'\bid="([A-Za-z0-9_\-]+)"', js))
    wanted = set(re.findall(r'\$\("([A-Za-z0-9_\-]+)"\)', js))
    missing = sorted(wanted - known)
    assert missing == [], f"the selector script looks up ids that are not in the page: {missing}"


def test_internal_links_point_to_pages_that_exist():
    served = {"/": INDEX, "/index.html": INDEX, "/guide.html": GUIDE, "/selector/selector-alpha.html": SELECTOR_HTML,
              "/selector/": SELECTOR_HTML}
    for page in PAGES:
        for href in parse(page).hrefs:
            if href.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target = href.split("#")[0].split("?")[0]
            assert target in served, f"{page.name}: link to {href} does not lead to a page of this project"


def test_external_links_use_https():
    for page in PAGES:
        for href in parse(page).hrefs:
            assert not href.startswith("http://"), f"{page.name}: {href}"


@pytest.mark.parametrize("path", [INDEX, GUIDE, SELECTOR_HTML, SELECTOR_JS], ids=lambda p: p.name)
def test_visible_text_has_no_em_or_en_dashes(path):
    """House rule: no dashes as punctuation anywhere in the software; a hyphen only joins two words."""
    text = path.read_text(encoding="utf8")
    hits = [m.start() for m in re.finditer("[\u2014\u2013]", text)]
    context = [text[max(0, i - 25):i + 25].replace("\n", " ") for i in hits[:3]]
    assert hits == [], f"{path.name}: {len(hits)} dash(es), for example {context}"


class VisibleText(HTMLParser):
    """The text a visitor can read: text nodes outside script, style and comments."""
    def __init__(self):
        super().__init__()
        self.skip, self.parts = 0, []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


@pytest.mark.parametrize("path", [INDEX, GUIDE, SELECTOR_HTML], ids=lambda p: p.name)
def test_visible_text_has_no_spaced_hyphens_used_as_dashes(path):
    parser = VisibleText()
    parser.feed(path.read_text(encoding="utf8"))
    text = " ".join(parser.parts)
    hits = re.findall(r".{20}\s-\s.{20}", text)
    assert hits == [], f"{path.name}: spaced hyphens as dashes, for example {hits[:2]}"


def test_the_guide_describes_the_options_the_builder_offers():
    """The guide must keep up with the dropdown options (these were missing or wrong before)."""
    guide = re.sub(r"<[^>]*>", " ", GUIDE.read_text(encoding="utf8"))
    for phrase in ("NCS 0.12", "NCS 0.45", "Targeting peptide", "SpyCatcher", "Intein", "Registry",
                   "BsaI", "BbsI", "COMMEC", "150 bp", "Overview"):
        assert phrase in guide, f"the guide no longer mentions {phrase!r}"
    assert "NCS with stop codon" not in guide.replace("There is one NCS sequence for all spacers", ""), "that option no longer exists"
    assert "As long as no real sequence of a promoter" not in guide, "the promoter has a real sequence now"


def test_no_leftover_references_to_removed_files():
    for path in (INDEX, GUIDE, ROOT / "README.md"):
        assert "PROJECT_TODO" not in path.read_text(encoding="utf8")


def test_the_builder_page_offers_no_option_the_backend_does_not_know():
    """Every dropdown value the builder can send for a slot is a kind resolve_slots accepts."""
    import sys
    sys.path.insert(0, str(ROOT))
    from Biologik.level0_design.slots import COMBINED_NCS, NC_SLOTS, resolve_slots

    text = INDEX.read_text(encoding="utf8")
    values = set(re.findall(r'<option value="(ncs[0-9]*|tp|custom)"', text)) | set(re.findall(r"""value="\$\{x\.id\}""", text))
    assert {"ncs", "tp", "custom"} <= values or "slotOptionsHtml" in text
    for kind in ("ncs", *COMBINED_NCS):
        n = COMBINED_NCS[kind][0] if kind in COMBINED_NCS else 1
        slots = resolve_slots({str(n): {"kind": kind}}, "nc")
        assert len(slots) == len(NC_SLOTS)


def test_the_level2_compatibility_hint_is_in_the_guide_and_in_the_builder_and_is_not_overstated():
    guide = re.sub(r"<[^>]*>", " ", GUIDE.read_text(encoding="utf8"))
    index = re.sub(r"<[^>]*>", " ", INDEX.read_text(encoding="utf8"))
    for text in (guide, index):
        assert "CCAA" in text and "AATG" in text and "BbsI" in text
        assert "not" in text.split("Which plasmids does")[1][:700]                   # says that it is not every Golden Gate plasmid
    assert "compatible with all Golden Gate" not in guide + index


def test_the_guide_explains_the_not_built_label():
    guide = re.sub(r"<[^>]*>", " ", GUIDE.read_text(encoding="utf8"))
    assert "(not built)" in guide and "has not been built yet" in guide
    assert "' (not built)'" in INDEX.read_text(encoding="utf8")                    # the label the guide explains is the one the builder shows


@pytest.mark.parametrize("path", [INDEX, GUIDE, SELECTOR_HTML], ids=lambda p: p.name)
def test_visible_text_never_mentions_stock(path):
    """Whether a plasmid is in stock is kept in the data files only; no page shows or even names it."""
    parser = VisibleText()
    parser.feed(path.read_text(encoding="utf8"))
    assert "stock" not in " ".join(parser.parts).lower()
    source = path.read_text(encoding="utf8").lower()
    assert "on_stock" not in source and "no_stock" not in source and "onstock" not in source


def test_the_documentation_does_not_mention_stock_either():
    for path in (ROOT / "README.md", ROOT / "Biologik" / "level0_design" / "parts" / "README.md"):
        assert "stock" not in path.read_text(encoding="utf8").lower(), path.name


def test_the_candidate_card_shows_sequence_data_before_the_source():
    js = SELECTOR_JS.read_text(encoding="utf8")
    card = js[js.index('<article class="candidate-card">'):]
    assert card.index("Sequence data (") < card.index('citationBlock("databank"')


def test_the_guide_advises_the_combined_ncs_for_two_neighbouring_spacers():
    guide = re.sub(r"<[^>]*>", " ", GUIDE.read_text(encoding="utf8"))
    assert "Prefer the combined NCS" in guide and "E. coli" in guide and "repeat" in guide


def test_the_empty_level2_backbone_names_its_cassette_tspurple():
    text = INDEX.read_text(encoding="utf8")
    assert "'tsPurple'" in text and "bp tsPurple cassette" in text
    assert "'Test cassette'" not in text and "bp test cassette" not in text


def test_the_builder_does_not_continue_when_the_screening_is_not_available():
    text = INDEX.read_text(encoding="utf8")
    gate = text[text.index("if(items.length && api && api.available && !(screening && screening.available))"):]
    assert "showCalcError(" in gate[:600] and "return;" in gate[:700]
    assert "skipping biosecurity screen" in text                                     # the failed call is still turned into 'not available' ...
    assert "screening = {available:false}" in text                                   # ... and the gate above stops the design


def test_the_pages_never_assume_a_remote_server():
    for path in (INDEX, GUIDE, ROOT / "README.md"):
        visible = re.sub(r"<[^>]*>", " ", path.read_text(encoding="utf8"))
        assert "builder's own server" not in visible and "Builder server" not in visible and "builder server" not in visible, path.name
        assert "with the server running" not in visible, path.name


def test_the_guide_names_the_intein_as_the_targeting_peptide_of_the_vault_and_points_to_the_registry():
    guide = re.sub(r"<[^>]*>", " ", GUIDE.read_text(encoding="utf8"))
    assert "Intein (INT)" in guide and "MVP" in guide
    assert "registry.igem.org" in GUIDE.read_text(encoding="utf8") and "Use your own sequence" in guide
    assert "has no targeting peptide of the toolkit either" not in guide


def test_the_builder_page_offers_the_intein_only_with_the_vault_and_the_guide_says_so():
    text = INDEX.read_text(encoding="utf8")
    assert "v.startsWith('intein:') && noIntHere" in text and "state.nc.id==='mvp'" in text
    guide = re.sub(r"<[^>]*>", " ", GUIDE.read_text(encoding="utf8"))
    assert "offered only when the human vault is the nanocompartment" in guide
