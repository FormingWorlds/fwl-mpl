"""Forming Worlds Lab matplotlib style.

Usage::

    import fwl_mpl
    fwl_mpl.use()          # light mode, white background (papers, docs)
    fwl_mpl.use("dark")    # dark mode (dark docs pages, slides)

or, without calling a function::

    plt.style.use("fwl_mpl.light")

Importing the package registers the bundled IBM Plex fonts and the Crameri
scientific colour maps (``cmc.*``), so the style sheets work on their own.

The categorical palette has 8 hues. Each mode has its own set, fitted so that
the closest pair stays at CAM02-UCS Delta E >= 12 for normal vision and for
full-severity deuteranomaly, protanomaly and tritanomaly, with at least 3:1
contrast against the light background and 4.5:1 against the dark one.
"""

import logging
from pathlib import Path

import cmcrameri.cm  # noqa: F401  (registers the cmc.* colour maps)
import matplotlib as mpl
from matplotlib import font_manager

__all__ = [
    "COLORMAPS",
    "CYCLE",
    "CYCLE_DARK",
    "MODES",
    "NAMES",
    "PALETTE",
    "SURFACES",
    "cmap",
    "colors",
    "panel_label",
    "register_fonts",
    "use",
]

__version__ = "0.1.0"

_HERE = Path(__file__).parent
_FONTS = _HERE / "fonts"

MODES = ("light", "dark")

# Cycle order: the first 4 hues are the most distinct pairs.
NAMES = ("azure", "vermilion", "emerald", "amber", "violet", "teal", "rose", "olive")

PALETTE = {
    "light": {
        "azure": "#008FF3",
        "vermilion": "#C94D45",
        "emerald": "#388E6A",
        "amber": "#C98702",
        "violet": "#6C3FB4",
        "teal": "#275F60",
        "rose": "#90003E",
        "olive": "#556C00",
    },
    "dark": {
        "azure": "#59B1EE",
        "vermilion": "#DC4C00",
        "emerald": "#B7E2B2",
        "amber": "#FCB71E",
        "violet": "#8A67F2",
        "teal": "#46999E",
        "rose": "#BA6384",
        "olive": "#98AB71",
    },
}

CYCLE = [PALETTE["light"][n] for n in NAMES]
CYCLE_DARK = [PALETTE["dark"][n] for n in NAMES]

# Neutrals per mode. "observed" is the colour for measured data points.
SURFACES = {
    "light": {
        "background": "#FFFFFF",
        "ink": "#17151F",
        "muted": "#615D70",
        "line": "#E1DFEA",
        "observed": "#2C2938",
    },
    "dark": {
        "background": "#0D0C17",
        "ink": "#ECEAF4",
        "muted": "#9C98AE",
        "line": "#2A2838",
        "observed": "#D2CFE0",
    },
}

# Crameri scientific colour maps by role. berlin has a dark midpoint, which
# reads as "zero" on a dark background; vik has a light one.
COLORMAPS = {
    "light": {"sequential": "cmc.batlow", "diverging": "cmc.vik", "cyclic": "cmc.romaO"},
    "dark": {"sequential": "cmc.batlow", "diverging": "cmc.berlin", "cyclic": "cmc.romaO"},
}


class _QuietFallbackWeight(logging.Filter):
    """Drop the notice that DejaVu Sans, the fallback for missing glyphs, has no Medium."""

    def filter(self, record):
        msg = record.getMessage()
        return not (msg.startswith("findfont: Failed to find font weight") and "DejaVu Sans" in msg)


_FILTER = _QuietFallbackWeight()


def _check_mode(mode):
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")


def register_fonts():
    """Register the bundled IBM Plex fonts with matplotlib for this session.

    Repeated calls are cheap: a font file that is already registered is skipped.

    Returns
    -------
    list of pathlib.Path
        The font files that this call registered.
    """
    known = {Path(f.fname) for f in font_manager.fontManager.ttflist}
    added = []
    for path in sorted(_FONTS.glob("*.ttf")):
        if path in known:
            continue
        font_manager.fontManager.addfont(str(path))
        added.append(path)
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

    Notes
    -----
    For more than 8 series, vary the line style or use a sequential colour
    map; more hues would break the colour-vision guarantee.
    """
    _check_mode(mode)
    cycle = CYCLE if mode == "light" else CYCLE_DARK
    if n is None:
        return list(cycle)
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

    Parameters
    ----------
    ax : matplotlib.axes.Axes
    label : str
    **kwargs
        Passed to :meth:`matplotlib.axes.Axes.text`; they override the defaults.

    Returns
    -------
    matplotlib.text.Text
    """
    opts = {
        "transform": ax.transAxes,
        "ha": "right",
        "va": "bottom",
        "fontweight": "medium",
        "fontsize": mpl.rcParams["axes.titlesize"],
    }
    opts.update(kwargs)
    return ax.text(-0.02, 1.03, label, **opts)


register_fonts()
logging.getLogger("matplotlib.font_manager").addFilter(_FILTER)
