"""Style sheets, fonts, the public helpers, and the rendered output."""

import importlib
import io
import json
import logging
import os
import re
import struct
import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import fwl_visual_language as fvl  # noqa: E402
import matplotlib as mpl  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pytest  # noqa: E402
from fwl_visual_language import mpl as fvl_mpl  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.colors import to_hex  # noqa: E402
from matplotlib.ft2font import FT2Font  # noqa: E402

import fwl_mpl  # noqa: E402

PKG = Path(fwl_mpl.__file__).parent
FONTS = fvl.fonts_dir() / "ttf"
GREEK = "αβγδεθκλμνπρστφχψωΓΔΘΛΣΦΨΩ"
# Glyphs that axis labels and tick labels commonly need, including U+2212 (minus).
SYMBOLS = "\u2212\u00b0\u00d7\u00b1\u00b7\u00b5\u00c5\u2013"
COLOUR_KEYS = re.compile(r"color|facecolor|edgecolor|prop_cycle")


@pytest.fixture(autouse=True)
def _reset_rc():
    yield
    plt.close("all")
    mpl.rcdefaults()


def hx(c):
    """Normalise a matplotlib colour value to upper-case '#RRGGBB'."""
    if isinstance(c, str) and len(c) == 6 and not c.startswith("#"):
        c = "#" + c
    return to_hex(c).upper()


def pdf_fonts(fig):
    """Base font names embedded in the PDF of a figure."""
    buf = io.BytesIO()
    fig.savefig(buf, format="pdf")
    return set(re.findall(rb"/BaseFont /(?:[A-Z]{6}\+)?([A-Za-z0-9_.-]+)", buf.getvalue()))


def strict_rc(mode):
    return mpl.rc_params_from_file(
        PKG / f"{mode}.mplstyle", fail_on_error=True, use_default_template=False
    )


# Style sheets


@pytest.mark.parametrize("mode", fwl_mpl.MODES)
def test_style_sheet_matches_palette_and_surfaces(mode):
    rc = strict_rc(mode)
    cycle = [hx(c) for c in rc["axes.prop_cycle"].by_key()["color"]]
    assert cycle == fwl_mpl.colors(mode=mode)
    s = fwl_mpl.SURFACES[mode]
    for key in ("figure.facecolor", "savefig.facecolor", "axes.facecolor"):
        assert hx(rc[key]) == s["background"]
    for key in (
        "text.color",
        "axes.labelcolor",
        "xtick.labelcolor",
        "ytick.labelcolor",
        "legend.labelcolor",
        "boxplot.boxprops.color",
        "boxplot.whiskerprops.color",
        "boxplot.capprops.color",
        "boxplot.flierprops.markeredgecolor",
    ):
        assert hx(rc[key]) == s["ink"], key
    for key in ("axes.edgecolor", "xtick.color", "ytick.color"):
        assert hx(rc[key]) == s["axis"]
    assert hx(rc["grid.color"]) == s["line"]
    assert rc["image.cmap"] == fwl_mpl.COLORMAPS[mode]["sequential"]


@pytest.mark.parametrize(("mode", "theme"), [("light", "paper"), ("dark", "dark")])
def test_style_sheets_are_the_token_sheets(mode, theme):
    # refresh: write fwl_visual_language.mpl.mplstyle(theme) to src/fwl_mpl/<mode>.mplstyle
    assert (PKG / f"{mode}.mplstyle").read_text(encoding="utf-8") == fvl_mpl.mplstyle(theme)


def test_style_sheets_are_valid_and_differ_only_in_colours():
    light, dark = strict_rc("light"), strict_rc("dark")
    assert set(light) == set(dark)
    assert set(light) <= set(mpl.rcParamsDefault)
    differ = {k for k in light if light[k] != dark[k]}
    assert differ and all(COLOUR_KEYS.search(k) for k in differ), differ


@pytest.mark.parametrize("mode", fwl_mpl.MODES)
def test_use_applies_mode(mode):
    fwl_mpl.use(mode)
    assert mpl.rcParams["font.family"][:2] == ["Geist", "Inter"]
    assert mpl.rcParams["font.monospace"][0] == "Geist Mono"
    cycle = [hx(c) for c in mpl.rcParams["axes.prop_cycle"].by_key()["color"]]
    assert cycle == fwl_mpl.colors(mode=mode)
    assert mpl.rcParams["pdf.fonttype"] == 42
    assert mpl.rcParams["ps.fonttype"] == 42
    assert mpl.rcParams["svg.fonttype"] == "path"
    assert mpl.rcParams["mathtext.fallback"] == "stixsans"
    assert hx(mpl.rcParams["axes.facecolor"]) == fwl_mpl.SURFACES[mode]["background"]


def test_use_rejects_unknown_mode():
    with pytest.raises(ValueError, match="mode must be one of"):
        fwl_mpl.use("white")


def test_saved_figure_keeps_its_size():
    fwl_mpl.use()
    fig, ax = plt.subplots()
    ax.plot([0, 1], [-1, 1])
    ax.set(xlabel="x", ylabel="y")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100)
    width, height = struct.unpack(">II", buf.getvalue()[16:24])
    assert (width, height) == (350, 260)


def test_style_sheet_works_without_use():
    code = (
        "import json, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt; "
        "plt.style.use('fwl_mpl.light'); import matplotlib as mpl; "
        "from matplotlib import font_manager as fm; "
        "p = fm.findfont(fm.FontProperties(family='Geist'), fallback_to_default=False); "
        "import cmcrameri.cm as cmc; name = mpl.rcParams['image.cmap']; "
        "same = mpl.colormaps[name](0.3) == cmc.batlow(0.3); "
        "print(json.dumps([name, same, p]))"
    )
    env = {**os.environ, "PYTHONPATH": str(PKG.parent)}
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
        env=env,
    )
    cmap_name, same, path = json.loads(out.stdout.strip().splitlines()[-1])
    assert cmap_name == "cmc.batlow"
    assert same
    assert Path(path).resolve() == (FONTS / "Geist-Regular.ttf").resolve()


def test_style_sheets_match_the_installed_tokens_at_import(recwarn):
    assert fwl_mpl._check_sheets() == []
    assert not [w for w in recwarn if "style sheets differ" in str(w.message)]


def test_a_sheet_that_differs_from_the_tokens_warns(monkeypatch):
    monkeypatch.setattr(fwl_mpl._fvl_mpl, "mplstyle", lambda theme: "")
    with pytest.warns(UserWarning, match="light, dark style sheets differ"):
        assert fwl_mpl._check_sheets() == ["light", "dark"]


def test_readme_colour_table_is_the_palette():
    path = Path(__file__).resolve().parents[1] / "README.md"
    if not path.is_file():
        pytest.skip("no README next to the tests (tests copied out of the repository)")
    readme = path.read_text(encoding="utf-8")
    rows = re.findall(r"^\| (\w+) \| `(#[0-9A-F]{6})` \| `(#[0-9A-F]{6})` \|$", readme, re.M)
    assert rows == [
        (n, fwl_mpl.PALETTE["light"][n], fwl_mpl.PALETTE["dark"][n]) for n in fwl_mpl.NAMES
    ]


# Fonts


def test_register_fonts_is_idempotent():
    assert fwl_mpl.register_fonts() == []


def test_register_fonts_adds_missing_files_and_puts_them_first():
    fm = font_manager.fontManager
    saved = list(fm.ttflist)
    try:
        bundled = [f for f in fm.ttflist if Path(f.fname).resolve().parent == FONTS.resolve()]
        fm.ttflist[:] = [f for f in fm.ttflist if f not in bundled]
        # A stand-in for a system copy of Geist at another path.
        fake = font_manager.FontEntry(
            fname="/nonexistent/Geist-Regular.ttf", name="Geist", weight=400
        )
        fm.ttflist.insert(0, fake)
        added = fwl_mpl.register_fonts()
        assert sorted(p.name for p in added) == sorted(p.name for p in FONTS.glob("*.ttf"))
        first = fm.ttflist[: len(added)]
        assert all(Path(f.fname).resolve().parent == FONTS.resolve() for f in first)
        assert fake in fm.ttflist
    finally:
        fm.ttflist[:] = saved
        fm._findfont_cached.cache_clear()


@pytest.mark.parametrize(
    ("family", "style", "weight", "fname"),
    [
        ("Geist", "normal", "normal", "Geist-Regular.ttf"),
        ("Geist", "italic", "normal", "Geist-Italic.ttf"),
        ("Geist", "normal", "medium", "Geist-Medium.ttf"),
        ("Geist", "italic", "medium", "Geist-MediumItalic.ttf"),
        ("Inter", "normal", "normal", "Inter-Regular.ttf"),
        ("Inter", "italic", "normal", "Inter-Italic.ttf"),
        ("Inter", "normal", "medium", "Inter-Medium.ttf"),
        ("Inter", "italic", "medium", "Inter-MediumItalic.ttf"),
        ("Geist Mono", "normal", "normal", "GeistMono-Regular.ttf"),
    ],
)
def test_bundled_fonts_resolve(family, style, weight, fname):
    prop = font_manager.FontProperties(family=family, style=style, weight=weight)
    path = font_manager.findfont(prop, fallback_to_default=False)
    assert Path(path).resolve() == (FONTS / fname).resolve()


TEXT_FILES = ["Geist-Regular.ttf", "Geist-Italic.ttf", "Geist-Medium.ttf", "Geist-MediumItalic.ttf"]
MATH_FILES = ["Inter-Regular.ttf", "Inter-Italic.ttf", "Inter-Medium.ttf", "Inter-MediumItalic.ttf"]


@pytest.mark.parametrize("fname", MATH_FILES)
def test_math_font_has_every_greek_command(fname):
    from matplotlib._mathtext_data import tex2uni

    charmap = FT2Font(str(FONTS / fname)).get_charmap()
    greek = {k: v for k, v in tex2uni.items() if 0x0370 <= v <= 0x03FF}
    assert len(greek) > 40
    assert [k for k, v in greek.items() if v not in charmap] == []
    assert [c for c in GREEK + SYMBOLS if ord(c) not in charmap] == []


@pytest.mark.parametrize("fname", TEXT_FILES)
def test_text_font_has_the_symbols_but_not_the_greek_the_tests_use(fname):
    # Geist has a few Greek letters (λ μ π Ω) only; the rest comes from Inter.
    charmap = FT2Font(str(FONTS / fname)).get_charmap()
    assert [c for c in SYMBOLS if ord(c) not in charmap] == []
    assert [c for c in "αρτφΔ" if ord(c) in charmap] == []


# Rendered PDF


def test_pdf_probe_detects_fallback_font():
    # Canary: a glyph that Geist and Inter lack must show up as a fallback font.
    fwl_mpl.use()
    fig = plt.figure()
    fig.text(0.1, 0.5, "☉")
    assert any(not f.startswith((b"Geist", b"Inter")) for f in pdf_fonts(fig))


@pytest.mark.parametrize("mode", fwl_mpl.MODES)
def test_pdf_embeds_geist_for_words_and_inter_for_math(mode):
    fwl_mpl.use(mode)
    fig, ax = plt.subplots()
    ax.plot([-2, 1], [-1, 1], label=r"$\rho\,\tau$ and $\phi$")
    ax.set_xlabel(r"Time, $t$ (Myr)")
    ax.set_ylabel(r"$\Delta T_\mathrm{max}$ (K)")
    ax.set_title("Mass fraction, α")
    ax.legend()
    fwl_mpl.panel_label(ax, "a")
    fonts = pdf_fonts(fig)
    want = {b"Geist-Regular", b"Geist-Medium", b"Inter-Regular", b"Inter-Italic"}
    assert want <= fonts, fonts
    assert all(f.startswith((b"Geist-", b"Inter-")) for f in fonts), fonts


def test_plain_text_greek_comes_from_inter():
    fwl_mpl.use()
    fig = plt.figure()
    fig.text(0.1, 0.5, "Δ")
    assert pdf_fonts(fig) == {b"Inter-Regular"}


def test_plain_greek_in_a_math_label_is_a_dummy_glyph(caplog):
    # matplotlib sets the text of a math label in the first family only, so the
    # README says to write Greek inside the math there.
    fwl_mpl.use()
    fig = plt.figure()
    fig.text(0.1, 0.5, r"$x$ and α")
    with caplog.at_level(logging.WARNING, logger="matplotlib.mathtext"):
        pdf_fonts(fig)
    assert any("does not have a glyph" in r.getMessage() for r in caplog.records)
    caplog.clear()
    fig.texts[0].set_text(r"$x$ and $\alpha$")
    with caplog.at_level(logging.WARNING, logger="matplotlib.mathtext"):
        pdf_fonts(fig)
    assert not any("does not have a glyph" in r.getMessage() for r in caplog.records)


def test_calligraphic_math_draws_the_inter_italic():
    fwl_mpl.use()
    fig = plt.figure()
    fig.text(0.1, 0.5, r"$\mathcal{L}$")
    assert pdf_fonts(fig) == {b"Inter-Italic"}


def test_math_fallback_is_sans():
    fwl_mpl.use()
    fig = plt.figure()
    fig.text(0.1, 0.5, r"$\nabla\phi$")
    fonts = pdf_fonts(fig)
    assert any(f.startswith(b"STIX") for f in fonts), fonts
    assert not any(f.lower().startswith(b"cm") for f in fonts), fonts


# Log filter


def _record(msg, args):
    return logging.LogRecord("matplotlib.font_manager", logging.WARNING, "", 0, msg, args, None)


def test_fallback_weight_notice_is_filtered_for_real_lookups(caplog):
    fm = font_manager.fontManager
    logger = logging.getLogger("matplotlib.font_manager")
    assert fwl_mpl._FILTER in logger.filters
    prop = font_manager.FontProperties(family="DejaVu Sans", weight="medium")
    try:
        logger.removeFilter(fwl_mpl._FILTER)
        fm._findfont_cached.cache_clear()
        with caplog.at_level(logging.WARNING, logger="matplotlib.font_manager"):
            font_manager.findfont(prop)
        unfiltered = [r for r in caplog.records if "Failed to find font weight" in r.msg]
        caplog.clear()
        logger.addFilter(fwl_mpl._FILTER)
        fm._findfont_cached.cache_clear()
        with caplog.at_level(logging.WARNING, logger="matplotlib.font_manager"):
            font_manager.findfont(prop)
        filtered = [r for r in caplog.records if "Failed to find font weight" in r.msg]
    finally:
        logger.addFilter(fwl_mpl._FILTER)
        fm._findfont_cached.cache_clear()
    if not unfiltered:
        pytest.skip("this matplotlib logs no fallback-weight notice for DejaVu Sans")
    assert filtered == []
    assert not fwl_mpl._FILTER.filter(unfiltered[0])


def test_reloading_the_package_keeps_one_filter():
    logger = logging.getLogger("matplotlib.font_manager")
    before = len(logger.filters)
    importlib.reload(fwl_mpl)
    assert len(logger.filters) == before
    assert fwl_mpl._FILTER in logger.filters


def test_fallback_weight_filter_message_forms():
    flt = fwl_mpl._FILTER
    three = "findfont: Failed to find font weight %s for %s, now using %s."
    two = "findfont: Failed to find font weight %s, now using %s."
    assert not flt.filter(_record(three, ("medium", "DejaVu Sans", 400)))
    assert flt.filter(_record(three, ("bold", "Geist", 500)))
    assert not flt.filter(_record(two, ("medium", 400)))
    assert flt.filter(_record(two, ("bold", 500)))
    assert flt.filter(_record("findfont: Font family 'Nope' not found.", None))
    assert flt.filter(_record("findfont: Failed to find font weight", None))


# Helpers


@pytest.mark.parametrize("mode", fwl_mpl.MODES)
def test_colors(mode):
    values = list(fwl_mpl.PALETTE[mode].values())
    assert fwl_mpl.colors(mode=mode) == values
    assert fwl_mpl.colors(1, mode) == values[:1]
    assert fwl_mpl.colors(3, mode) == values[:3]
    assert fwl_mpl.colors(8, mode) == values


@pytest.mark.parametrize("n", [0, 9, -1])
def test_colors_rejects_out_of_range(n):
    with pytest.raises(ValueError, match="n must be between 1 and 8"):
        fwl_mpl.colors(n)


@pytest.mark.parametrize("n", [2.5, "3"])
def test_colors_rejects_non_integers(n):
    with pytest.raises(TypeError, match="as an integer"):
        fwl_mpl.colors(n)


def test_colors_rejects_unknown_mode():
    with pytest.raises(ValueError, match="mode must be one of"):
        fwl_mpl.colors(2, "sepia")


@pytest.mark.parametrize(
    ("mode", "role", "name"),
    [
        ("light", "sequential", "cmc.batlow"),
        ("light", "diverging", "cmc.vik"),
        ("light", "cyclic", "cmc.romaO"),
        ("dark", "sequential", "cmc.batlow"),
        ("dark", "diverging", "cmc.berlin"),
        ("dark", "cyclic", "cmc.romaO"),
    ],
)
def test_cmap_roles(mode, role, name):
    got, want = fwl_mpl.cmap(role, mode), mpl.colormaps[name]
    assert [got(x) for x in (0.0, 0.3, 1.0)] == [want(x) for x in (0.0, 0.3, 1.0)]


def test_cmap_rejects_unknown_role():
    with pytest.raises(ValueError, match="role must be one of"):
        fwl_mpl.cmap("qualitative")


def _lift_pt(ax, t):
    """Offset of a panel label from its anchor (-0.02, 1) in axes coordinates, in points."""
    anchor = ax.transAxes.transform((-0.02, 1.0))
    at = t.get_transform().transform(t.get_position())
    return tuple((at - anchor) * 72 / ax.figure.dpi)


def test_panel_label_defaults_and_override():
    fwl_mpl.use()
    fig, ax = plt.subplots()
    t = fwl_mpl.panel_label(ax, "b")
    assert t.get_text() == "b"
    assert t.get_position() == pytest.approx((-0.02, 1.0))
    assert _lift_pt(ax, t) == pytest.approx((0.0, 6.0))  # half of 8 pt tick labels, plus 2
    assert t.get_horizontalalignment() == "right"
    assert t.get_verticalalignment() == "bottom"
    assert t.get_fontweight() in ("medium", 500)
    assert t.get_fontsize() == pytest.approx(9.5)
    t2 = fwl_mpl.panel_label(ax, "c", ha="left", color="red", size=12, weight="bold")
    assert t2.get_horizontalalignment() == "left"
    assert t2.get_color() == "red"
    assert t2.get_fontsize() == pytest.approx(12)
    assert t2.get_fontweight() == "bold"


def test_panel_label_honours_fontproperties_and_fontdict():
    fwl_mpl.use()
    fig, ax = plt.subplots()
    props = font_manager.FontProperties(size=14, weight="bold")
    t = fwl_mpl.panel_label(ax, "a", fontproperties=props)
    assert (t.get_fontsize(), t.get_fontweight()) == (14.0, "bold")
    t = fwl_mpl.panel_label(ax, "b", fontdict={"size": 13, "color": "red"})
    assert (t.get_fontsize(), t.get_color()) == (13.0, "red")
    t = fwl_mpl.panel_label(ax, "c", fontdict={"size": 13}, size=11)
    assert t.get_fontsize() == 11.0
    assert fwl_mpl.panel_label(ax, "d").get_fontweight() == "medium"


@pytest.mark.parametrize("height", [1.2, 2.6, 5.0])
def test_panel_label_clears_a_labelled_upper_y_end(height):
    fwl_mpl.use()
    fig, ax = plt.subplots(figsize=(3.5, height))
    ax.plot([0, 8], [0, 3000])
    fwl_mpl.label_ends(ax)
    fwl_mpl.panel_label(ax, "a")
    assert fwl_mpl.check_figure(fig) == []


def test_panel_label_follows_the_tick_label_size():
    fwl_mpl.use()
    with mpl.rc_context({"ytick.labelsize": 12}):
        fig, ax = plt.subplots()
        t = fwl_mpl.panel_label(ax, "a")
    assert _lift_pt(ax, t) == pytest.approx((0.0, 8.0))
    fig, ax = plt.subplots()
    ax.tick_params(axis="y", labelsize=10)
    t = fwl_mpl.panel_label(ax, "a")
    assert _lift_pt(ax, t) == pytest.approx((0.0, 7.0))


def test_panel_label_lift_is_in_points_at_any_resolution():
    fwl_mpl.use()
    fig, ax = plt.subplots()
    t = fwl_mpl.panel_label(ax, "a")
    fig.set_dpi(300)
    assert _lift_pt(ax, t) == pytest.approx((0.0, 6.0))


def test_panel_label_on_3d_axes():
    fwl_mpl.use()
    fig = plt.figure()
    ax = fig.add_subplot(projection="3d")
    t = fwl_mpl.panel_label(ax, "d")
    assert t.get_text() == "d"
    assert _lift_pt(ax, t) == pytest.approx((0.0, 6.0))


def test_bold_italic_math_uses_inter():
    fwl_mpl.use()
    if "mathtext.bfit" not in mpl.rcParams:
        pytest.skip("matplotlib before 3.8 has no \\mathbfit")
    fig = plt.figure()
    fig.text(0.1, 0.5, r"$\mathbfit{x}$")
    assert pdf_fonts(fig) == {b"Inter-MediumItalic"}


@pytest.mark.parametrize("mode", fwl_mpl.MODES)
def test_text_sizes_are_the_ones_the_readme_states(mode):
    fwl_mpl.use(mode)
    rc = mpl.rcParams
    sizes = [rc[k] for k in ("xtick.labelsize", "ytick.labelsize", "legend.fontsize")]
    assert sizes == [8, 8, 8]
    assert (rc["axes.labelsize"], rc["axes.titlesize"]) == (9, 9.5)
