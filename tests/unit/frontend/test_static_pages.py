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
              "/selector/": SELECTOR_HTML,
              "/selector/overview.html": ROOT / "encapsulin_selector" / "overview.html",
              "/selector/builder-filter.html": ROOT / "encapsulin_selector" / "builder-filter.html"}
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
    for phrase in ("NCS 0.12", "NCS 0.45", "Targeting peptide", "SpyCatcher", "INT", "Registry",
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
    assert "not" in guide.split("Which plasmids does")[1][:700]                      # the guide says that it is not every Golden Gate plasmid
    assert "not every Golden Gate plasmid" in index                                  # so does the short text of the info window
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
    assert "Prefer the combined NCS" in guide and "E. coli" in guide and "S. cerevisiae" in guide and "repeat" in guide


def test_the_empty_level2_backbone_names_its_cassette_tspurple():
    text = INDEX.read_text(encoding="utf8")
    assert "'tsPurple'" in text and "bp tsPurple cassette" in text
    assert "'Test cassette'" not in text and "bp test cassette" not in text


def test_the_builder_does_not_calculate_a_construct_when_the_screening_is_not_available():
    """With own sequences the screening call decides, with toolkit parts only the status of the screening does."""
    text = INDEX.read_text(encoding="utf8")
    gate = text[text.index("  let screening=null, proceed=true;"):text.index("  let flaggedCount=0;")]
    assert "api.screenSequences(items)" in gate and "api.commecStatus()" in gate
    assert "if(!screeningUp)" in gate and "showCalcError(" in gate and "return;" in gate
    assert "no construct can be calculated" in gate
    assert 'try again.\', true);' in gate                                                               # shown without the prefix "The design could not be calculated:"
    assert "plain ? message" in text
    assert "skipping biosecurity screen" in gate and "screening = {available:false}" in gate               # a failed screening call counts as not available
    assert "does not calculate a construct" in text and "does not continue with" not in text


def test_the_pages_never_assume_a_remote_server():
    for path in (INDEX, GUIDE, ROOT / "README.md"):
        visible = re.sub(r"<[^>]*>", " ", path.read_text(encoding="utf8"))
        assert "builder's own server" not in visible and "Builder server" not in visible and "builder server" not in visible, path.name
        assert "with the server running" not in visible, path.name


def test_the_guide_names_the_intein_as_the_targeting_peptide_of_the_vault_and_points_to_the_registry():
    guide = re.sub(r"<[^>]*>", " ", GUIDE.read_text(encoding="utf8"))
    assert "intein INT" in guide and "MVP" in guide
    assert "registry.igem.org" in GUIDE.read_text(encoding="utf8") and "Use your own sequence" in guide
    assert "has no targeting peptide of the toolkit either" not in guide


def test_the_builder_page_has_no_separate_intein_choice_because_int_is_the_targeting_peptide_of_the_vault():
    text = INDEX.read_text(encoding="utf8")
    assert "group('Intein" not in text and "noIntHere" not in text


def test_the_module_headings_of_both_sites_carry_no_fused_in_front_or_behind_note():
    text = INDEX.read_text(encoding="utf8")
    for heading in ("N-terminus of the shell", "C-terminus of the shell", "C-terminus of the cargo", "N-terminus of the cargo"):
        assert heading in text
    assert not re.search(r"<small>Type 0\.[145] &amp; 0\.[245]", text)                  # the notes now live in the info buttons of the sites


def test_the_info_buttons_of_both_sites_say_which_types_are_the_n_and_the_c_terminus():
    text = INDEX.read_text(encoding="utf8")
    nc = text[text.index("  nc: { title:'What is a nanocompartment?'"):text.index("  cargo: { title:'Cargo / gene of interest'")]
    cargo = text[text.index("  cargo: { title:'Cargo / gene of interest'"):text.index("  stop: { title:")]
    assert "Type 0.1 and 0.2 form the <b>N-terminus of the shell</b> and are fused in front of the shell" in nc
    assert "Type 0.4 and 0.5 form the <b>C-terminus of the shell</b> and are fused behind the shell" in nc
    assert "Type 0.4 and 0.5 form the <b>N-terminus of the cargo</b> and are fused in front of the cargo" in cargo
    assert "Type 0.1 and 0.2 form the <b>C-terminus of the cargo</b> and are fused behind the cargo" in cargo


THEME_PAGES = [INDEX, GUIDE, SELECTOR_HTML, ROOT / "encapsulin_selector" / "overview.html", ROOT / "encapsulin_selector" / "builder-filter.html"]
SUN = '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M5 19l1.5-1.5M17.5 6.5L19 5"/>'
MOON = '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>'


@pytest.mark.parametrize("page", THEME_PAGES, ids=lambda p: p.name)
def test_every_page_has_the_same_light_dark_switch(page):
    """Same label (Light or Dark), the same sun and moon icon and the same stored value on every page."""
    text = page.read_text(encoding="utf8")
    if page == SELECTOR_HTML:
        text += SELECTOR_JS.read_text(encoding="utf8")
    if page.name == "builder-filter.html":
        text += (page.parent / "builder-filter.js").read_text(encoding="utf8")
    assert 'id="themeToggle"' in text and 'id="themeIcon"' in text and 'id="themeLabel"' in text
    assert SUN in text and MOON in text, f"{page.name}: sun or moon icon missing or malformed"
    assert "'Dark'" in text.replace('"', "'") and "'Light'" in text.replace('"', "'")
    assert "encore.theme" in text


def test_the_builder_header_has_an_overview_button_next_to_the_screening_badge_that_opens_the_guide():
    text = INDEX.read_text(encoding="utf8")
    link = text.index('id="overviewLink"')
    assert 'href="/guide.html"' in text[link - 60:link + 120] and "<span>Overview</span>" in text[link:link + 500]
    assert link < text.index('id="commecStatus"') < text.index('id="themeToggle"')


def test_every_page_uses_the_font_of_the_wiki_and_loads_no_web_font():
    """One typeface on the whole site, the one of the toolKIT wiki (Segoe UI, Helvetica, Arial): no web fonts are loaded."""
    pages = [INDEX, GUIDE, SELECTOR_HTML, ROOT / "encapsulin_selector" / "overview.html", ROOT / "encapsulin_selector" / "builder-filter.html",
             ROOT / "frontend" / "site.css", ROOT / "encapsulin_selector" / "selector-alpha.css", ROOT / "encapsulin_selector" / "overview.css"]
    for page in pages:
        text = page.read_text(encoding="utf8")
        assert "Grotesk" not in text and "JetBrains" not in text and "fonts.googleapis.com" not in text and "fonts.gstatic.com" not in text, page.name
        assert "'Inter'" not in text and "font-family: Inter" not in text and "font-family:Inter" not in text, page.name
    assert '"Segoe UI",Helvetica,Arial,sans-serif' in (ROOT / "frontend" / "site.css").read_text(encoding="utf8")
    assert '"Segoe UI",Helvetica,Arial,sans-serif' in (ROOT / "encapsulin_selector" / "selector-alpha.css").read_text(encoding="utf8")



def test_builder_and_filter_share_the_wiki_colours():
    """The chrome colours of the Builder (site.css) and of the Filter (selector-alpha.css) come from the toolKIT wiki and agree."""
    site = (ROOT / "frontend" / "site.css").read_text(encoding="utf8")
    filt = (ROOT / "encapsulin_selector" / "selector-alpha.css").read_text(encoding="utf8")
    for color in ("#1F342E", "#17261F", "#1C8070", "#F0F5F3", "#DDE9E5", "#111A18", "#2BBFA6", "#DCE5E2"):
        assert color.lower() in site.lower() and color.lower() in filt.lower(), color
    for old in ("#12283a", "#0072B2", "#3fa9d8"):
        assert old.lower() not in site.lower() and old.lower() not in filt.lower(), old


DYSLEXIA_PAGES = [INDEX, GUIDE, SELECTOR_HTML, ROOT / "encapsulin_selector" / "overview.html", ROOT / "encapsulin_selector" / "builder-filter.html"]


@pytest.mark.parametrize("page", DYSLEXIA_PAGES, ids=lambda p: p.name)
def test_every_page_offers_the_dyslexia_mode(page):
    text = page.read_text(encoding="utf8")
    assert '<link rel="stylesheet" href="/dyslexia.css">' in text and '<script src="/dyslexia.js"></script>' in text
    assert 'id="themeToggle"' in text                                               # the script puts its button in front of the theme switch


def test_the_dyslexia_mode_ships_the_font_and_does_not_load_it_from_another_server():
    fonts = ROOT / "frontend" / "fonts" / "opendyslexic"
    for name in ("regular", "bold", "italic", "bolditalic"):
        data = (fonts / f"opendyslexic-{name}.woff2").read_bytes()
        assert data[:4] == b"wOF2" and len(data) > 50_000, name                     # a real WOFF2 file
    assert "SIL Open Font License" in (fonts / "LICENSE.txt").read_text(encoding="utf8")
    css = (ROOT / "frontend" / "dyslexia.css").read_text(encoding="utf8")
    assert css.count("@font-face") == 4 and "http" not in css                       # four faces, all from this project
    js = (ROOT / "frontend" / "dyslexia.js").read_text(encoding="utf8")
    assert "encore.dyslexia" in js and "enc-dyslexic" in js and "aria-pressed" in js
    assert "enc-dyslexic" in css and "dyslexiaToggle" in css
    guide = re.sub(r"<[^>]*>", " ", GUIDE.read_text(encoding="utf8"))
    assert "Dyslexia-friendly font" in guide


def test_the_promoter_step_has_the_field_label_only_and_no_extra_promoter_heading_above_it():
    text = INDEX.read_text(encoding="utf8")
    body = text[text.index('<div id="body2">'):text.index('id="promoter"')]
    assert 'class="grouplab"' not in body and body.count("Promoter") == 1


def test_the_download_boxes_of_the_three_levels_carry_no_explaining_note():
    text = INDEX.read_text(encoding="utf8")
    for gone in ("no need to open every module separately", "Record names end in", "GenBank files of the finished construct"):
        assert gone not in text
    for box in ("Level 0 downloads", "Level 1 downloads", "Level 2 downloads"):
        assert box in text                                                           # the boxes and their buttons stay
    assert "Download GenBank (.gb)" in text and "Module sequences (.gb)" in text and "Level 2 plasmid (.gb)" in text


def test_the_how_this_level_works_texts_live_in_the_info_button_next_to_golden_gate_assembly():
    text = INDEX.read_text(encoding="utf8")
    assert "How this level works" not in text and "lvlinfo" not in text and "l1fold" not in text       # no separate button in the level tabs
    for gone in ("data-info=\"level0\"", "data-info=\"level1\"", "data-info=\"level2\""):
        assert gone not in text
    info = text[text.index("  levels: { title:'Level 0 → 1 → 2'"):text.index("  codonOpt: { title:")]
    for part in ("Level 0 (BbsI)", "Level 1 (BsaI)", "Level 2 (BbsI)"):
        assert part in info, part
    assert "Level 1 → 2 (BsaI)" not in info                                                              # the old text named the wrong enzyme for Level 2
    assert 'data-info="levels"' in text and text.count("Golden Gate assembly<button") == 1
    guide = GUIDE.read_text(encoding="utf8")                                                             # the full text sits in the guide
    for part in ("Level 0 · individual parts (BbsI).", "Level 1 · modules (BsaI).", "Level 2 · finished construct (BbsI).",
                 "Which plasmids does this insert fit?", "Basis of the assembly."):
        assert part in guide, part


INFO_TO_GUIDE = {"primers": "bg-primers", "levels": "bg-levels", "codonOpt": "bg-codon", "commec": "bg-commec", "stop": "bg-stop"}


def test_the_long_info_windows_are_short_and_point_to_the_full_text_in_the_overview():
    text = INDEX.read_text(encoding="utf8")
    start = text.index("const INFO = {")
    block = text[start:text.index("\n};", start)]
    entries = dict(re.findall(r"\n  ([A-Za-z0-9]+): \{ title(.*?)(?=\n  [A-Za-z0-9]+: \{ title|\Z)", block, flags=re.S))
    guide = GUIDE.read_text(encoding="utf8")
    for key, anchor in INFO_TO_GUIDE.items():
        body = re.sub(r"<[^>]+>", " ", entries[key])
        assert len(body.split()) <= 160, f"{key}: {len(body.split())} words"                              # short enough to read at a glance
        assert f'href="/guide.html#{anchor}"' in entries[key], key
        assert f'id="{anchor}"' in guide, anchor
    for key in ("nc", "cargo", "promoter"):                                                              # the short windows are in the guide as well
        assert f'id="bg-{ {"nc": "nc", "cargo": "cargo", "promoter": "promoter"}[key] }"' in guide
    assert 'id="background"' in guide and 'href="#background"' in guide


def test_the_steps_in_the_left_bar_show_only_their_titles_without_a_subtitle():
    text = INDEX.read_text(encoding="utf8")
    bar = text[text.index('<nav class="stepper" id="stepper">'):text.index("</nav>", text.index('<nav class="stepper" id="stepper">'))]
    titles = re.findall(r'<span class="t">([^<]*)</span>', bar)
    assert titles == ["Nanocompartment Site", "Cargo Site", "Promoter", "Result", "Overview"]
    assert 'class="sub"' not in bar and ".s-text .sub" not in text


def test_the_shell_and_the_cargo_fields_carry_no_choose_or_use_your_own_hint():
    text = INDEX.read_text(encoding="utf8")
    assert "choose from library or use your own" not in text and "choose an example or use your own" not in text
    assert "Nanocompartment · Type 0.3" in text and "Cargo · Type 0.3" in text      # the labels stay


def test_the_type_cards_of_both_sites_show_only_the_type_without_n_or_c_terminal_label():
    text = INDEX.read_text(encoding="utf8")
    card = text[text.index("function slotCardHtml"):]
    card = card[:card.index("</div>")]
    assert 'class="stype">Type 0.${n}</span>' in card
    assert "sterm" not in text and "N-terminal'" not in text and "'C-terminal'" not in text


def test_the_readme_says_that_nothing_is_calculated_without_the_screening():
    readme = (ROOT / "README.md").read_text(encoding="utf8")
    assert "does not calculate a construct" in readme or "does not calculate any construct" in readme
    assert "the Builder already works, just without" not in readme and "runs without the screening container" not in readme


def test_the_info_windows_show_no_graphic_placeholder():
    text = INDEX.read_text(encoding="utf8")
    for gone in ("Graphic placeholder", "Custom graphic to be added", "pop-img", "popImg", "ph-tag"):
        assert gone not in text, gone
    start = text.index("const INFO = {")
    block = text[start:text.index("\n};", start)]
    assert "img:" not in block and "Diagram:" not in block                      # no caption of a graphic is kept in the data either
    assert len(re.findall(r"\n  [A-Za-z0-9]+: \{ title:", block)) == 8
    assert 'id="popTitle"' in text and 'id="popText"' in text and 'id="popClose"' in text


def test_the_filter_hint_is_a_button_on_the_right_in_the_row_of_the_shell_facts():
    text = INDEX.read_text(encoding="utf8")
    row = text[text.index('<div class="nc-metarow">'):text.index('<div id="customNc"')]
    assert 'id="ncMeta"' in row and 'id="filterBtn"' in row and 'href="/selector/builder-filter.html"' in row
    assert row.index('id="ncMeta"') < row.index('id="filterBtn"')                      # the facts first, the button after them on the right
    assert "Find more nanocompartments here" in row
    assert ".filterbtn{" in text and "margin-left:auto" in text[text.index(".filterbtn{"):text.index(".filterbtn{") + 400]
    assert "helplink" not in text and "Not sure which fits" not in text            # the old line below the cards is gone
