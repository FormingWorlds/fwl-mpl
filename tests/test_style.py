"""Style sheets, fonts, the public helpers, and the rendered PDF."""

import io
import logging
import re
import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib as mpl  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pytest  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.colors import to_hex  # noqa: E402
from matplotlib.ft2font import FT2Font  # noqa: E402

import fwl_mpl  # noqa: E402

PKG = Path(fwl_mpl.__file__).parent
GREEK = "αβγδεθκλμνπρστφχψωΓΔΘΛΣΦΨΩ"


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
    return set(re.findall(rb"/BaseFont /(?:[A-Z]{6}\+)?([A-Za-z0-9-]+)", buf.getvalue()))


@pytest.mark.parametrize("mode", fwl_mpl.MODES)
def test_style_sheet_matches_palette_and_surfaces(mode):
    rc = mpl.rc_params_from_file(PKG / f"{mode}.mplstyle", use_default_template=False)
    cycle = [hx(c) for c in rc["axes.prop_cycle"].by_key()["color"]]
    assert cycle == fwl_mpl.colors(mode=mode)
    s = fwl_mpl.SURFACES[mode]
    for key in ("figure.facecolor", "savefig.facecolor", "axes.facecolor"):
        assert hx(rc[key]) == s["background"]
    for key in ("text.color", "axes.labelcolor", "xtick.labelcolor", "legend.labelcolor"):
        assert hx(rc[key]) == s["ink"]
    for key in ("axes.edgecolor", "xtick.color", "ytick.color"):
        assert hx(rc[key]) == s["muted"]
    assert hx(rc["grid.color"]) == s["line"]
    assert rc["image.cmap"] == fwl_mpl.COLORMAPS[mode]["sequential"]


@pytest.mark.parametrize("mode", fwl_mpl.MODES)
def test_use_applies_mode(mode):
    fwl_mpl.use(mode)
    assert mpl.rcParams["font.family"][0] == "IBM Plex Sans"
    cycle = [hx(c) for c in mpl.rcParams["axes.prop_cycle"].by_key()["color"]]
    assert cycle == fwl_mpl.colors(mode=mode)
    assert mpl.rcParams["pdf.fonttype"] == 42


def test_use_rejects_unknown_mode():
    with pytest.raises(ValueError, match="mode must be one of"):
        fwl_mpl.use("white")


def test_register_fonts_is_idempotent():
    assert fwl_mpl.register_fonts() == []


@pytest.mark.parametrize(
    ("style", "weight", "fname"),
    [
        ("normal", "normal", "IBMPlexSans-Regular.ttf"),
        ("italic", "normal", "IBMPlexSans-Italic.ttf"),
        ("normal", "medium", "IBMPlexSans-Medium.ttf"),
    ],
)
def test_bundled_fonts_resolve(style, weight, fname):
    prop = font_manager.FontProperties(family="IBM Plex Sans", style=style, weight=weight)
    path = font_manager.findfont(prop, fallback_to_default=False)
    assert Path(path) == PKG / "fonts" / fname


@pytest.mark.parametrize("fname", ["IBMPlexSans-Regular.ttf", "IBMPlexSans-Italic.ttf"])
def test_bundled_sans_covers_greek(fname):
    charmap = FT2Font(str(PKG / "fonts" / fname)).get_charmap()
    assert [c for c in GREEK if ord(c) not in charmap] == []


def test_pdf_probe_detects_fallback_font():
    # Canary: a glyph IBM Plex Sans lacks must show up as a fallback font.
    fwl_mpl.use()
    fig = plt.figure()
    fig.text(0.1, 0.5, "⊕")
    assert any(not f.startswith(b"IBMPlex") for f in pdf_fonts(fig))


@pytest.mark.parametrize("mode", fwl_mpl.MODES)
def test_pdf_embeds_only_plex_for_text_and_math(mode):
    fwl_mpl.use(mode)
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1], label=r"$\rho\,\tau$")
    ax.set_xlabel(r"Time, $t$ (Myr)")
    ax.set_ylabel(r"$\Delta T_\mathrm{max}$ (K) and $\varphi$")
    ax.legend()
    fwl_mpl.panel_label(ax, "a")
    fonts = pdf_fonts(fig)
    assert fonts and all(f.startswith(b"IBMPlexSans") for f in fonts), fonts


def test_style_sheet_works_without_use():
    code = (
        "import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt; "
        "plt.style.use('fwl_mpl.light'); import matplotlib as mpl; "
        "from matplotlib import font_manager as fm; "
        "p = fm.findfont(fm.FontProperties(family='IBM Plex Sans'), fallback_to_default=False); "
        "print(mpl.rcParams['image.cmap'], p)"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    cmap_name, path = out.stdout.split()
    assert cmap_name == "cmc.batlow"
    assert Path(path).name == "IBMPlexSans-Regular.ttf"


@pytest.mark.parametrize("mode", fwl_mpl.MODES)
def test_colors(mode):
    assert fwl_mpl.colors(mode=mode) == list(fwl_mpl.PALETTE[mode].values())
    assert fwl_mpl.colors(3, mode) == list(fwl_mpl.PALETTE[mode].values())[:3]


@pytest.mark.parametrize("n", [0, 9])
def test_colors_rejects_out_of_range(n):
    with pytest.raises(ValueError, match="n must be between 1 and 8"):
        fwl_mpl.colors(n)


def test_colors_rejects_unknown_mode():
    with pytest.raises(ValueError, match="mode must be one of"):
        fwl_mpl.colors(2, "sepia")


@pytest.mark.parametrize("mode", fwl_mpl.MODES)
@pytest.mark.parametrize("role", ["sequential", "diverging", "cyclic"])
def test_cmap_roles(mode, role):
    assert fwl_mpl.cmap(role, mode).name == fwl_mpl.COLORMAPS[mode][role]


def test_cmap_diverging_differs_by_mode():
    assert fwl_mpl.cmap("diverging", "light").name == "cmc.vik"
    assert fwl_mpl.cmap("diverging", "dark").name == "cmc.berlin"


def test_cmap_rejects_unknown_role():
    with pytest.raises(ValueError, match="role must be one of"):
        fwl_mpl.cmap("qualitative")


def test_panel_label_position_and_override():
    fwl_mpl.use()
    fig, ax = plt.subplots()
    t = fwl_mpl.panel_label(ax, "b")
    assert t.get_text() == "b"
    assert t.get_position() == (-0.02, 1.03)
    assert t.get_transform() is ax.transAxes
    assert t.get_horizontalalignment() == "right"
    t2 = fwl_mpl.panel_label(ax, "c", ha="left", color="red")
    assert t2.get_horizontalalignment() == "left"
    assert t2.get_color() == "red"


def _record(msg):
    return logging.LogRecord("matplotlib.font_manager", logging.WARNING, "", 0, msg, None, None)


def test_fallback_weight_notice_is_filtered():
    flt = fwl_mpl._FILTER
    assert flt in logging.getLogger("matplotlib.font_manager").filters
    assert not flt.filter(
        _record("findfont: Failed to find font weight medium for DejaVu Sans, now using 400.")
    )
    assert flt.filter(_record("findfont: Font family 'Nope' not found."))
    assert flt.filter(
        _record("findfont: Failed to find font weight medium for Arial, now using 400.")
    )
