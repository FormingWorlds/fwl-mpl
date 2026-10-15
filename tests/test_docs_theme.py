"""Documenter.jl theme: contrast of the derived text colours, scoping, and installation."""

import re
import runpy
import sys

import pytest

import fwl_mpl
from fwl_mpl import docs_theme

MODES = ("light", "dark")


def test_contrast_reference_values():
    assert docs_theme.contrast("#000000", "#FFFFFF") == pytest.approx(21.0)
    assert docs_theme.contrast("#777777", "#777777") == pytest.approx(1.0)


def test_mix_end_points_and_midpoint():
    assert docs_theme._mix("#000000", "#FFFFFF", 0) == "#000000"
    assert docs_theme._mix("#000000", "#FFFFFF", 1) == "#FFFFFF"
    assert docs_theme._mix("#000000", "#FFFFFF", 0.5) == "#808080"


@pytest.mark.parametrize("mode", MODES)
def test_text_colours_reach_aa_on_both_surfaces(mode):
    t = docs_theme._tokens(mode)
    for name, colour in {**t["safe"], "muted": t["muted"], "ink": t["ink"]}.items():
        for surface in (t["bg"], t["sub"]):
            assert docs_theme.contrast(colour, surface) >= 4.5, name


@pytest.mark.parametrize("mode", MODES)
def test_text_safe_keeps_a_colour_that_already_passes(mode):
    t = docs_theme._tokens(mode)
    ok = t["safe"]["teal"] if mode == "light" else t["safe"]["emerald"]
    assert docs_theme._text_safe(ok, t["ink"], (t["bg"], t["sub"])) == ok


def test_text_safe_falls_back_to_ink_when_no_mix_passes():
    assert docs_theme._text_safe("#777777", "#777777", ("#777777",)) == "#777777"


def test_fill_colours_are_the_figure_palette():
    css = docs_theme.documenter_css()
    for mode in MODES:
        for name, colour in fwl_mpl.PALETTE[mode].items():
            assert f"--fwl-{name}-fill: {colour};" in css


def test_both_modes_define_every_variable():
    css = docs_theme.documenter_css()
    names = set(re.findall(r"(--fwl-[a-z-]+):", css))
    light_block, dark_block = (
        css.split(f"{sel} {{\n", 1)[1].split("}\n", 1)[0]
        for sel in docs_theme._MODE_SELECTOR.values()
    )
    for block in (light_block, dark_block):
        assert set(re.findall(r"(--fwl-[a-z-]+):", block)) == names


def test_every_variable_used_is_defined():
    css = docs_theme.documenter_css()
    defined = set(re.findall(r"(--fwl-[a-z-]+):", css))
    used = set(re.findall(r"var\((--fwl-[a-z-]+)\)", css))
    assert used <= defined


def test_every_rule_sits_under_the_two_mode_scope():
    css = docs_theme.documenter_css()
    body = css.split("}\n", 3 + len(docs_theme._FONT_FACES))[-1]
    selectors = [b.split("{")[0] for b in body.split("}\n") if "{" in b]
    selectors = [s for s in selectors if not s.lstrip().startswith("html")]
    assert selectors
    for sel in selectors:
        for line in sel.strip().split(",\n"):
            assert line.startswith(docs_theme._SCOPE), line


def test_font_files_named_in_the_stylesheet_ship_with_the_package():
    css = docs_theme.documenter_css()
    files = re.findall(rf'url\("{docs_theme.FONT_DIR}/([^"]+)"\)', css)
    assert len(files) == len(docs_theme._FONT_FACES)
    for f in files:
        assert (fwl_mpl._FONTS / f).is_file()


def test_install_writes_stylesheet_fonts_and_licence(tmp_path):
    out = docs_theme.install_documenter_theme(tmp_path / "assets")
    assert out == tmp_path / "assets" / "fwl.css"
    assert out.read_text(encoding="utf-8") == docs_theme.documenter_css()
    fonts = tmp_path / "assets" / docs_theme.FONT_DIR
    assert (fonts / "OFL.txt").is_file()
    assert (fonts / "IBMPlexSans-Regular.ttf").stat().st_size > 10_000


def test_install_is_idempotent(tmp_path):
    first = docs_theme.install_documenter_theme(tmp_path).read_bytes()
    second = docs_theme.install_documenter_theme(tmp_path).read_bytes()
    assert first == second


def test_command_line_installs_and_prints_the_path(tmp_path, capsys):
    docs_theme.main([str(tmp_path / "a")])
    assert capsys.readouterr().out.strip() == str(tmp_path / "a" / "fwl.css")
    assert (tmp_path / "a" / "fwl.css").is_file()


def test_module_runs_as_a_script(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["fwl_mpl.docs_theme", str(tmp_path)])
    monkeypatch.delitem(sys.modules, "fwl_mpl.docs_theme")
    runpy.run_module("fwl_mpl.docs_theme", run_name="__main__")
    assert (tmp_path / "fwl.css").is_file()


def test_light_theme_is_scoped_by_absence_of_a_theme_class_and_dark_by_its_class():
    css = docs_theme.documenter_css()
    assert 'html:not([class*="theme--"]), html.theme--documenter-light {' in css
    assert "html.theme--documenter-dark {" in css
    scope = (
        ':is(html:not([class*="theme--"]), '
        "html.theme--documenter-light, html.theme--documenter-dark)"
    )
    assert f"{scope} .content h1" in css


@pytest.mark.parametrize("mode", MODES)
def test_text_safe_colours_keep_their_hue_instead_of_collapsing_to_ink(mode):
    t = docs_theme._tokens(mode)
    assert all(colour != t["ink"] for colour in t["safe"].values())
