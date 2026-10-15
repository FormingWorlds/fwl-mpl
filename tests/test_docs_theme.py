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
def test_text_colours_reach_aa_on_every_surface(mode):
    t = docs_theme._tokens(mode)
    surfaces = [t["bg"], t["sub"], t["hover"], *t["washes"].values()]
    assert len(surfaces) == 11
    for name, colour in {**t["safe"], "muted": t["muted"], "ink": t["ink"]}.items():
        for surface in surfaces:
            assert docs_theme.contrast(colour, surface) >= 4.5, name


@pytest.mark.parametrize("mode", MODES)
def test_washes_in_the_stylesheet_are_the_ones_checked(mode):
    css = docs_theme.documenter_css()
    block = css.split(docs_theme._MODE_SELECTOR[mode] + " {\n", 1)[1].split("}\n", 1)[0]
    for name, wash in docs_theme._tokens(mode)["washes"].items():
        assert f"--fwl-{name}-wash: {wash};" in block


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


def _blocks(css):
    """Split the stylesheet into (selector text, body) pairs, header comment removed."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return [(m[1].strip(), m[2]) for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css)]


def test_stylesheet_structure_and_scope():
    blocks = _blocks(docs_theme.documenter_css())
    faces = [b for b in blocks if b[0] == "@font-face"]
    modes = [b for b in blocks if b[0] in docs_theme._MODE_SELECTOR.values()]
    rules = [b for b in blocks if b not in faces and b not in modes]
    assert (len(faces), len(modes), len(rules)) == (5, 2, len(docs_theme._RULES))
    for selector, body in rules:
        for line in selector.split(",\n"):
            assert line.startswith(docs_theme._SCOPE + " "), line
        decls = [d.strip() for d in body.strip().split(";") if d.strip()]
        assert decls and all(re.fullmatch(r"[a-z-]+: .+", d) for d in decls), selector


@pytest.mark.parametrize("mode", MODES)
def test_mode_block_sets_page_background_and_no_faux_styles(mode):
    blocks = dict(_blocks(docs_theme.documenter_css()))
    body = blocks[docs_theme._MODE_SELECTOR[mode]]
    assert "background-color: var(--fwl-bg);" in body
    assert "font-synthesis: none;" in body


def test_admonition_kinds_are_the_ones_documenter_emits():
    # Documenter 1.19 HTMLWriter: note/info -> is-info, tip -> is-success, plus
    # is-warning, is-danger, is-compat, is-todo; anything else gets no kind class.
    assert set(docs_theme._ADMONITIONS) == {
        "info",
        "success",
        "warning",
        "danger",
        "compat",
        "todo",
    }
    css = docs_theme.documenter_css()
    assert f"{docs_theme._SCOPE} .admonition {{" in css
    for kind, hue in docs_theme._ADMONITIONS.items():
        rule = css.split(f"{docs_theme._SCOPE} .admonition.is-{kind} {{", 1)[1].split("}", 1)[0]
        assert f"border-color: var(--fwl-{hue}-fill);" in rule
        assert f"background-color: var(--fwl-{hue}-wash);" in rule


def test_header_names_the_package_and_documenter_versions():
    head = docs_theme.documenter_css().splitlines()[0]
    assert f"fwl-mpl {fwl_mpl.__version__}" in head
    assert "Documenter.jl 1.19" in head


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
def test_text_safe_takes_the_smallest_step_toward_ink(mode):
    t = docs_theme._tokens(mode)
    moved = 0
    for name, hue in t["hues"].items():
        steps = [docs_theme._mix(hue, t["ink"], k / 100) for k in range(101)]
        k = steps.index(t["safe"][name])
        assert k <= 50, name  # still closer to the palette hue than to ink
        if k:
            moved += 1
            prev = steps[k - 1]
            assert min(docs_theme.contrast(prev, s) for s in t["surfaces"]) < 4.5, name
    assert moved >= 1


def test_light_azure_is_darkened_for_text():
    # #008FF3 is 3.4:1 on white, below the 4.5:1 that text needs.
    assert docs_theme.contrast("#008FF3", "#FFFFFF") < 4.5
    assert docs_theme._tokens("light")["link"] != "#008FF3"


def test_install_into_a_file_path_raises(tmp_path):
    target = tmp_path / "assets"
    target.write_text("not a folder")
    with pytest.raises(OSError):
        docs_theme.install_documenter_theme(target)
