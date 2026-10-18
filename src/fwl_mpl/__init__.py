"""Forming Worlds Lab matplotlib style.

Usage::

    import fwl_mpl
    fwl_mpl.use()          # light mode, white background (papers, docs)
    fwl_mpl.use("dark")    # dark mode (dark docs pages, slides)

or, without calling a function::

    plt.style.use("fwl_mpl.light")

Importing the package registers the Geist and Inter fonts of
``fwl-visual-language`` and the Crameri scientific colour maps (``cmc.*``), so
the style sheets work on their own.

Colours, fonts and the style sheets come from the lab tokens in
``fwl-visual-language``: the light mode is its ``paper`` theme, the dark mode its
``dark`` theme. The categorical palette has 8 hues per mode; the closest pair
stays at CAM02-UCS Delta E >= 14.9 (light) and >= 10.9 (dark) for normal vision
and for full-severity deuteranomaly, protanomaly and tritanomaly, with at least
3:1 contrast against the light background and 4.5:1 against the dark one.
"""

import logging
import operator
from pathlib import Path

import cmcrameri.cm  # noqa: F401  (registers the cmc.* colour maps)
import fwl_visual_language as fvl
import matplotlib as mpl
from matplotlib import cbook, font_manager
from matplotlib.text import Text
from matplotlib.transforms import ScaledTranslation

__all__ = [
    "COLORMAPS",
    "CYCLE",
    "CYCLE_DARK",
    "MODES",
    "NAMES",
    "PALETTE",
    "SURFACES",
    "check_figure",
    "cmap",
    "colorbar",
    "colors",
    "finish",
    "label_ends",
    "panel_label",
    "register_fonts",
    "round_limits",
    "use",
]

__version__ = "0.2.0"

_HERE = Path(__file__).parent
_FONTS = fvl.fonts_dir() / "ttf"

MODES = ("light", "dark")

# Token theme per mode of this package.
_THEME = {"light": "paper", "dark": "dark"}

# Fixed cycle order: series k always gets the k-th colour.
NAMES = tuple(fvl.tokens()["palette"]["names"])

PALETTE = {mode: dict(fvl.palette(theme)) for mode, theme in _THEME.items()}

CYCLE = [PALETTE["light"][n] for n in NAMES]
CYCLE_DARK = [PALETTE["dark"][n] for n in NAMES]

# Ink step for measured data points; it stays at Delta E >= 12 from every
# palette colour under the same vision conditions (heading is too close to
# the dark "ink" hue).
_OBSERVED = {"light": "ink-950", "dark": "ink-50"}


def _surfaces(mode):
    r = fvl.roles(_THEME[mode])
    return {
        "background": r["background"],
        "ink": r["heading"],
        "muted": r["muted"],
        "axis": r["axis"],
        "line": r["line"],
        "observed": fvl.color(_OBSERVED[mode]),
    }


SURFACES = {mode: _surfaces(mode) for mode in _THEME}

# Crameri scientific colour maps by role. berlin has a dark midpoint, which
# reads as "zero" on a dark background; vik has a light one.
_MAPS = fvl.tokens()["colormaps"]["default"]
COLORMAPS = {
    mode: {
        "sequential": f"cmc.{_MAPS['sequential']}",
        "diverging": f"cmc.{_MAPS['diverging_' + mode]}",
        "cyclic": "cmc.romaO",
    }
    for mode in _THEME
}


class _QuietFallbackWeight(logging.Filter):
    """Drop the notice that DejaVu Sans, the fallback for missing glyphs, has no Medium.

    matplotlib passes (weight, family, fallback weight), or (weight, fallback weight)
    before 3.11.2. Geist and Inter have a Medium, so in the 2-argument form a medium
    request that falls back to 400 comes from DejaVu Sans.
    """

    def filter(self, record):
        if not str(record.msg).startswith("findfont: Failed to find font weight"):
            return True
        args = record.args if isinstance(record.args, tuple) else ()
        if len(args) == 3:
            return args[1] != "DejaVu Sans"
        if len(args) == 2:
            return not (str(args[0]) in ("medium", "500") and args[1] == 400)
        return True


_FILTER = _QuietFallbackWeight()


def _check_mode(mode):
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")


def register_fonts():
    """Register the Geist, Geist Mono and Inter fonts with matplotlib for this session.

    Repeated calls are cheap: a font file that is already registered is skipped.

    Returns
    -------
    list of pathlib.Path
        The font files that this call registered.
    """
    ttflist = font_manager.fontManager.ttflist
    known = {Path(f.fname).resolve() for f in ttflist}
    added = []
    for path in sorted(_FONTS.glob("*.ttf")):
        if path.resolve() in known:
            continue
        font_manager.fontManager.addfont(str(path))
        added.append(path)
    # findfont takes the first exact match, so these files go before any system
    # copy of the same fonts.
    fonts_dir = _FONTS.resolve()
    ours = [f for f in ttflist if Path(f.fname).resolve().parent == fonts_dir]
    ids = {id(f) for f in ours}
    ttflist[:] = ours + [f for f in ttflist if id(f) not in ids]
    return added


def use(mode="light"):
    """Apply the Forming Worlds Lab style to all following figures.

    Parameters
    ----------
    mode : {"light", "dark"}, default "light"
        "light" draws on white for papers and light docs pages. "dark" draws
        on the dark background for dark docs pages and slides.

    Raises
    ------
    ValueError
        If ``mode`` is not "light" or "dark".
    """
    _check_mode(mode)
    import matplotlib.pyplot as plt

    register_fonts()
    plt.style.use(str(_HERE / f"{mode}.mplstyle"))
    # matplotlib 3.8 added this key, so it cannot go in the style sheets.
    if "mathtext.bfit" in mpl.rcParams:
        mpl.rcParams["mathtext.bfit"] = f"{fvl.tokens()['fonts']['math']}:italic:medium"


def colors(n=None, mode="light"):
    """Return the first ``n`` colours of the categorical cycle.

    Parameters
    ----------
    n : int, optional
        Number of colours, 1 to 8. All 8 when omitted.
    mode : {"light", "dark"}, default "light"

    Returns
    -------
    list of str
        Hex colour strings in cycle order.

    Raises
    ------
    ValueError
        If ``n`` is outside 1 to 8 or ``mode`` is unknown.
    TypeError
        If ``n`` is not an integer.

    Notes
    -----
    For more than 8 series, vary the line style or use a sequential colour
    map; more hues would break the colour-vision guarantee.
    """
    _check_mode(mode)
    cycle = CYCLE if mode == "light" else CYCLE_DARK
    if n is None:
        return list(cycle)
    n = operator.index(n)
    if not 1 <= n <= len(cycle):
        raise ValueError(f"n must be between 1 and {len(cycle)}, got {n}")
    return list(cycle[:n])


def cmap(role="sequential", mode="light"):
    """Return the colour map for a data role.

    Parameters
    ----------
    role : {"sequential", "diverging", "cyclic"}, default "sequential"
    mode : {"light", "dark"}, default "light"

    Returns
    -------
    matplotlib.colors.Colormap

    Raises
    ------
    ValueError
        If ``role`` or ``mode`` is unknown.
    """
    _check_mode(mode)
    roles = COLORMAPS[mode]
    if role not in roles:
        raise ValueError(f"role must be one of {tuple(roles)}, got {role!r}")
    return mpl.colormaps[roles[role]]


def panel_label(ax, label, **kwargs):
    """Write a panel label ("a", "b", ...) above the top-left corner of an axes.

    The label sits half a y tick label plus 2 pt above the axes, so it clears a
    labelled upper end of the y axis at any axes height.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
    label : str
    **kwargs
        Text properties, aliases such as ``size`` included; they override the
        defaults. A ``fontdict`` is read as well, with ``kwargs`` winning. A
        ``fontproperties`` object replaces the default size and weight. On 3D axes
        the label is placed with ``text2D``.

    Returns
    -------
    matplotlib.text.Text
    """
    tick_pt = font_manager.FontProperties(size=mpl.rcParams["ytick.labelsize"]).get_size_in_points()
    lift = ScaledTranslation(0, (tick_pt / 2 + 2) / 72, ax.figure.dpi_scale_trans)
    opts = {
        "transform": ax.transAxes + lift,
        "horizontalalignment": "right",
        "verticalalignment": "bottom",
        "fontweight": "medium",
        "fontsize": mpl.rcParams["axes.titlesize"],
    }
    user = cbook.normalize_kwargs(kwargs, Text)
    fontdict = cbook.normalize_kwargs(user.pop("fontdict", None), Text)
    user = {**fontdict, **user}
    if "fontproperties" in user:
        del opts["fontsize"], opts["fontweight"]
    opts.update(user)
    text = getattr(ax, "text2D", ax.text)
    return text(-0.02, 1.0, label, **opts)


from .layout import check_figure, colorbar, finish, label_ends, round_limits  # noqa: E402

register_fonts()
_logger = logging.getLogger("matplotlib.font_manager")
for _old in [f for f in _logger.filters if type(f).__name__ == "_QuietFallbackWeight"]:
    _logger.removeFilter(_old)
_logger.addFilter(_FILTER)
