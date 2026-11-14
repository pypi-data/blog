import re

import pytest
import xml.etree.ElementTree as ET

from svgchart import columns, hbar

ROWS = [("openai", 12261.0), ("mcp (MCP SDK)", 22982.0), ("ollama", 1281.0)]
MONTHS = [("Nov 25", 5.6), ("Dec 25", 8.2), ("Nov 26*", 6.9)]


def charts():
    return [
        hbar(ROWS, title="Projects", unit="projects"),
        columns(MONTHS, title="Share", unit="%", fmt="{:.1f}"),
    ]


def test_every_value_labelled():
    s = hbar(ROWS, title="Projects", unit="projects")
    for v in ("12,261", "22,982", "1,281"):
        assert f">{v}<" in s
    c = columns(MONTHS, title="Share", unit="%", fmt="{:.1f}")
    for v in ("5.6", "8.2", "6.9"):
        assert f">{v}<" in c


def test_aria_lists_values():
    s = hbar(ROWS, title="Projects", unit="projects")
    aria = re.search(r'aria-label="([^"]*)"', s).group(1)
    assert aria.startswith("Projects:")
    assert "mcp (MCP SDK) 22,982" in aria and "openai 12,261" in aria


def test_no_hex_colours():
    for s in charts():
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b", s)


def test_valid_xml():
    for s in charts():
        root = ET.fromstring(s)
        assert root.tag.endswith("svg")
        assert "viewBox" in root.attrib


def test_font_sizes_at_least_22():
    for s in charts():
        sizes = [float(x) for x in re.findall(r'font-size="([\d.]+)"', s)]
        assert sizes and min(sizes) >= 22


def test_chart_text_at_least_12px_on_a_phone():
    # The post column is 328 px wide on a 360 px phone (16 px gutters).
    for s in charts():
        vw = float(re.search(r'viewBox="0 0 ([\d.]+) ', s).group(1))
        sizes = [float(x) for x in re.findall(r'font-size="([\d.]+)"', s)]
        assert min(sizes) * 328 / vw >= 12


CARD_ROWS = [
    ("Most imported AI SDK", [("22,982", "import mcp, the MCP SDK", "win"),
                              ("12,261", "import openai", "")]),
    ("LLM SDK share, peak", [("8.8%", "Apr 2026", "")]),
]


def make_card():
    from svgchart import card
    return card(CARD_ROWS, title="What new PyPI packages import", sub="Data as of 13 Nov 2026",
                note="The MCP SDK leads.", foot="Latest release of 335,167 projects")


def test_card_values_setup_and_aria():
    s = make_card()
    assert ">22,982 ✓<" in s              # a win gets a check mark
    assert ">12,261<" in s                  # neutral: no mark
    assert ">8.8%<" in s and ">Apr 2026<" in s
    aria = re.search(r'aria-label="([^"]*)"', s).group(1)
    for v in ("22,982", "12,261", "8.8%", "Apr 2026", "The MCP SDK leads.", "335,167"):
        assert v in aria


def test_card_win_is_green_and_neutral_is_not():
    s = make_card()
    assert s.count('fill="var(--win)"') == 1


def test_card_valid_xml_no_hex_fonts_22():
    s = make_card()
    ET.fromstring(s)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", s)
    sizes = [float(x) for x in re.findall(r'font-size="([\d.]+)"', s)]
    assert min(sizes) >= 22


def test_card_text_inside_viewbox():
    # every text baseline sits above the bottom of the viewBox
    s = make_card()
    h = float(re.search(r'viewBox="0 0 \d+ ([\d.]+)"', s).group(1))
    ys = [float(y) for y in re.findall(r'<text x="[\d.]+" y="([\d.]+)"', s)]
    assert max(ys) < h


def test_card_png_inlines_every_var():
    card_png = pytest.importorskip("card_png")  # site-only helper, not in the public repo
    css_vars, inline_vars, CSS = card_png.css_vars, card_png.inline_vars, card_png.CSS
    out = inline_vars(make_card(), css_vars(CSS.read_text()))
    assert "var(--" not in out


def test_wide_card_is_landscape():
    from svgchart import card
    s = card(CARD_ROWS, title="T", sub="S", note="N", foot="F", width=1200)
    w, h = map(float, re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', s).groups())
    assert w > h


def test_narrow_card_text_at_least_12px_on_a_phone():
    # On a 360 px phone the post column is 328 px wide (16 px gutters).
    s = make_card()
    vw = float(re.search(r'viewBox="0 0 ([\d.]+) ', s).group(1))
    sizes = [float(x) for x in re.findall(r'font-size="([\d.]+)"', s)]
    assert min(sizes) * 328 / vw >= 12
