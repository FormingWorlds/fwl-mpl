"""Layout rules for lab figures: labelled axis ends and no text on data.

Every axis and every colour bar shows a number at both ends, so a reader sees
the range it covers. Call :func:`finish` on a figure before saving it: it rounds
automatic axis limits outward to tick values, labels the ends of limits set by
hand and of colour bars, and returns what :func:`check_figure` still finds::

    problems = fwl_mpl.finish(fig)
    assert not problems, "\\n".join(problems)

:func:`check_figure` reports text, tick labels and legends that overlap data
lines, markers, error bars, axis lines, colour bars or each other, and axes or
colour bars whose ends carry no number. Moving a legend or a label is left to the author.
"""

import math
from contextlib import contextmanager
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_EVEN, Context, Decimal, localcontext

import matplotlib as mpl
import numpy as np
from matplotlib.backends.backend_agg import RendererAgg
from matplotlib.collections import LineCollection, PathCollection
from matplotlib.colors import LogNorm, Normalize
from matplotlib.contour import ContourSet
from matplotlib.legend import Legend
from matplotlib.projections.polar import PolarAxes
from matplotlib.text import Annotation, Text
from matplotlib.ticker import (
    AutoLocator,
    AutoMinorLocator,
    FixedLocator,
    FuncFormatter,
    LogFormatter,
    LogFormatterSciNotation,
    LogLocator,
    MaxNLocator,
    MultipleLocator,
    NullFormatter,
    ScalarFormatter,
)
from matplotlib.transforms import Bbox

__all__ = ["check_figure", "colorbar", "finish", "label_ends", "round_limits"]

# Text boxes shrink by this many pixels before a test, so text that only
# touches a line does not count as a collision.
_SLACK_PX = 1.0
# An end counts as labelled when a labelled tick lies within this fraction of
# the axis span from it.
_END_TOL = 1e-6
# An inner tick closer to an end than this fraction of the tick step is dropped,
# so its label does not run into the end label.
_CROWD = 0.75
# An image or mesh edge this close to a tick, as a fraction of the span, is
# snapped to the tick; a mesh drawn from cell centres overhangs by half a cell.
_SNAP = 0.02
# Rounding may widen an axis or a colour range by at most this fraction of the
# data span; past it an axis keeps the data limits and a colour bar rounds digits.
_MAX_GROW = 0.1
# Significant digits of an end label; colour bar ends are rounded to at most this many.
_LABEL_DIGITS = 6
# A value within this fraction of a rounded value counts as on it; float32 data
# are off by up to 6e-8 (a float32 0.7 is 0.699999988).
_DIGIT_TOL = Decimal("1e-7")
_DECIMAL = Context(  # every field set, so no global decimal setting applies
    prec=40,
    rounding=ROUND_HALF_EVEN,
    Emin=-999999,
    Emax=999999,
    capitals=1,
    clamp=0,
    flags=[],
    traps=[],
)
# Matplotlib widens a colour range narrower than this fraction of its largest end,
# and replaces one whose ends are both smaller than _SMALLEST.
_TINY = 1e-15
_SMALLEST = 1e6 / _TINY * np.finfo(float).tiny


def _nice_ticks(vmin, vmax, nbins=5):
    """Return tick values that cover [vmin, vmax], first <= vmin, last >= vmax."""
    return MaxNLocator(nbins=nbins, steps=[1, 2, 2.5, 5, 10]).tick_values(vmin, vmax)


def _round_limits(vmin, vmax, log=False):
    """Expand a range outward to tick values; return (lo, hi, ticks)."""
    if log:
        lo = 10.0 ** math.floor(math.log10(vmin))
        hi = max(10.0 ** math.ceil(math.log10(vmax)), 10 * lo)
        return lo, hi, _end_ticks(lo, hi, log=True)
    ticks = _nice_ticks(vmin, vmax)
    tol = 1e-9 * (vmax - vmin)  # a tick at 0.30000000000000004 counts as 0.3
    lo = min(ticks[ticks <= vmin + tol].max(), vmin)
    hi = max(ticks[ticks >= vmax - tol].min(), vmax)
    return lo, hi, ticks[(ticks >= lo - tol) & (ticks <= hi + tol)]


def _round_digits(value, digits, up):
    """Round ``value`` up or down to ``digits`` significant digits.

    A value within _DIGIT_TOL of a rounded value goes to that value, also when it
    lies on the other side; callers keep the data inside with min and max.
    """
    if value == 0 or not math.isfinite(value):
        return float(value) + 0.0  # -0.0 becomes 0.0
    with localcontext(_DECIMAL):
        d = Decimal(repr(float(value)))  # the shortest decimal: 3.3, not 3.29999...
        exp = d.adjusted() - digits + 1
        q = d.scaleb(-exp)
        tol = abs(q) * _DIGIT_TOL
        k = (q - tol if up else q + tol).to_integral_value(ROUND_CEILING if up else ROUND_FLOOR)
        return float(k.scaleb(exp))


def _singular(vmin, vmax):
    """Return whether a colour bar would widen [vmin, vmax], as matplotlib's nonsingular does."""
    if not (np.isfinite(vmin) and np.isfinite(vmax)):
        return True
    big = max(abs(vmin), abs(vmax))
    return big < _SMALLEST or vmax - vmin <= _TINY * big


def _label_is_exact(value):
    """Return whether the end label shows ``value`` without rounding."""
    return math.isclose(float(format(value, f".{_LABEL_DIGITS}g")), value, rel_tol=1e-12)


def _digit_limits(vmin, vmax):
    """Expand a range outward to significant digits per end; return (lo, hi) or None.

    The digit count is the smallest from 2 to _LABEL_DIGITS that gives 2 different
    rounded ends and widens the span by at most _MAX_GROW; None when none does. An
    end within _DIGIT_TOL of a rounded value keeps the data value.
    """
    for digits in range(2, _LABEL_DIGITS + 1):
        down = _round_digits(vmin, digits, up=False)
        up = _round_digits(vmax, digits, up=True)
        lo, hi = min(down, vmin), max(up, vmax)
        if down < up and hi - lo <= (1 + _MAX_GROW) * (vmax - vmin):
            return lo, hi
    return None


def _end_ticks(vmin, vmax, nbins=5, log=False, labelled=True):
    """Ticks inside [vmin, vmax] plus both ends; drop inner ticks that crowd an end.

    On a logarithmic scale the inner ticks are powers of ten, spaced in decades.
    With ``labelled`` (the ticks get _end_label), a linear scale also drops inner
    ticks that the label cannot show exactly or that print like an end.
    """
    if log:
        lo, hi = math.log10(vmin), math.log10(vmax)
        ticks = np.log10(LogLocator(numticks=nbins + 2).tick_values(vmin, vmax))
    else:
        lo, hi = vmin, vmax
        ticks = _nice_ticks(vmin, vmax, nbins)
    inner = ticks[(ticks > lo) & (ticks < hi)]
    step = ticks[1] - ticks[0] if len(ticks) > 1 else (hi - lo)
    keep = inner[(inner - lo > _CROWD * step) & (hi - inner > _CROWD * step)]
    if not log:
        # An end that is zero but for rounding error is labelled 0.
        noise = 64 * np.finfo(float).eps * max(abs(vmin), abs(vmax))
        vmin = 0.0 if abs(vmin) <= noise else vmin
        vmax = 0.0 if abs(vmax) <= noise else vmax
    if not log and labelled:
        # A 6-digit label shows 1000.005, and an end at 1000.0078, as 1000.01.
        ends = {_end_label(vmin), _end_label(vmax)}
        exact = [_label_is_exact(t) and _end_label(t) not in ends for t in keep]
        keep = keep[np.array(exact, dtype=bool)]
    return np.concatenate([[vmin], 10.0**keep if log else keep, [vmax]])


def _minor_locator(vmin, vmax, nbins, name, ndivs=None):
    """Minor ticks on the step of the inner major ticks, divided as AutoMinorLocator does."""
    ticks = _nice_ticks(vmin, vmax, nbins)
    step = ticks[1] - ticks[0]
    if ndivs is None:
        ndivs = mpl.rcParams.get(f"{name}tick.minor.ndivs", "auto")
    if ndivs == "auto":
        mantissa = step / 10 ** math.floor(math.log10(step))
        ndivs = 5 if np.isclose(mantissa, [1, 2.5, 5, 10]).any() else 4
    return MultipleLocator(step / ndivs)


def _end_label(value, pos=None):
    """Format a tick value compactly, with the typographic minus of the style."""
    text = format(value, f".{_LABEL_DIGITS}g")
    if mpl.rcParams["axes.unicode_minus"]:
        text = text.replace("-", "\N{MINUS SIGN}")
    return text


def colorbar(mappable, *, ax=None, ends="round", **kwargs):
    """Add a colour bar whose lowest and highest colours carry a number.

    Parameters
    ----------
    mappable : matplotlib.cm.ScalarMappable
        The image, mesh or contour set the colour bar describes.
    ax : matplotlib.axes.Axes or list of Axes, optional
        Axes to take space from, as in ``Figure.colorbar``; defaults to the axes
        of ``mappable``.
    ends : {"round", "label"}
        ``"round"`` widens the colour range outward to tick values, so both ends
        are round numbers. On a linear norm this happens only when it widens the
        range by at most a tenth; otherwise each end is rounded outward to 2
        significant digits and labelled, with up to 6 digits when 2 would widen
        the range by more than a tenth, and tick values again when 6 still would.
        An end within a relative 1e-7 of a rounded value keeps the data value
        and shows the rounded one. A logarithmic norm goes to whole decades, a
        contour set keeps its levels, and other norms keep their range, with
        the end values as ticks. ``"label"`` keeps the range and adds the end
        values as ticks, labelled to 6 significant digits; use it when the
        range itself matters, such as a symmetric diverging range. With a
        6-digit label, inner ticks that it cannot show, or that print like an
        end, are left out.
    **kwargs
        Passed to ``Figure.colorbar`` (``cax``, ``label``, ``pad``, ``shrink``,
        ...). ``ticks`` and ``format`` given here are kept.

    Returns
    -------
    matplotlib.colorbar.Colorbar

    Raises
    ------
    ValueError
        If ``ends`` is not one of the two modes, if neither ``ax``, ``cax`` nor
        the mappable names an axes, or if a log norm has neither data nor limits.
    """
    if ends not in ("round", "label"):
        raise ValueError(f"ends must be 'round' or 'label', got {ends!r}")
    if ax is None:
        ax = getattr(mappable, "axes", None)
    host = ax if kwargs.get("cax") is None else kwargs["cax"]
    if host is None:
        raise ValueError("the mappable is on no axes; pass ax or cax")
    if mappable.get_array() is not None:
        mappable.autoscale_None()
    norm = mappable.norm
    if not norm.scaled():
        if isinstance(norm, LogNorm):
            raise ValueError("a log norm without data needs vmin and vmax")
        mappable.set_clim(0, 1)  # as Figure.colorbar does for a mappable without data
    vmin, vmax = norm.vmin, norm.vmax
    log = isinstance(norm, LogNorm)
    if log and not (np.isfinite(vmin) and vmin > 0):
        raise ValueError(f"a log norm needs a positive vmin, got {vmin}")
    exact = ends == "label"
    own = "format" not in kwargs  # the ticks get _end_label when exact
    if (
        ends == "round"
        and type(norm) in (Normalize, LogNorm)
        and not isinstance(mappable, ContourSet)
    ):
        lo, hi, ticks = _round_limits(vmin, vmax, log=log)
        digit = None
        if not log and hi - lo > (1 + _MAX_GROW) * (vmax - vmin):
            digit = _digit_limits(vmin, vmax)
        if digit is not None and not _singular(*digit):
            lo, hi = digit
            ticks, exact = _end_ticks(lo, hi, labelled=own), True
        vmin, vmax = lo, hi
        mappable.set_clim(vmin, vmax)
    else:
        ticks = _end_ticks(vmin, vmax, log=log, labelled=exact and own)
    cb = np.ravel(host)[0].figure.colorbar(mappable, ax=ax, **kwargs)
    cb.outline.set_visible(False)
    if "ticks" not in kwargs:
        cb.set_ticks(ticks)
    if exact and own:
        cb.formatter = FuncFormatter(_end_label)
    cb._fwl_ends = True
    return cb


def label_ends(ax, axis="both"):
    """Put labelled ticks on both limits of an axis whose limits were set by hand.

    Call it after the last change to the limits: the ticks it sets are fixed.
    On a logarithmic axis the inner ticks are powers of ten and minor ticks carry
    no label. On a linear axis, inner ticks that a 6-digit label cannot show, or
    that print like an end, are left out, and default minor ticks follow the
    step of the major tick grid.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
    axis : {"both", "x", "y"}

    Raises
    ------
    ValueError
        If ``axis`` is not one of the three names.
    """
    if axis not in ("both", "x", "y"):
        raise ValueError(f"axis must be 'both', 'x' or 'y', got {axis!r}")
    for name in ("x", "y"):
        if axis in ("both", name):
            axis_ = getattr(ax, f"{name}axis")
            lo, hi = sorted(getattr(ax, f"get_{name}lim")())
            nbins = max(1, min(5, axis_.get_tick_space() - 1))
            log = axis_.get_scale() == "log"
            getattr(ax, f"set_{name}ticks")(_end_ticks(lo, hi, nbins, log=log))
            axis_.set_major_formatter(FuncFormatter(_end_label))
            minor = axis_.get_minor_locator()
            if log and type(axis_.get_minor_formatter()) in (LogFormatter, LogFormatterSciNotation):
                axis_.set_minor_formatter(NullFormatter())  # minor labels would mix formats
            elif not log and isinstance(minor, AutoMinorLocator):
                axis_.set_minor_locator(_minor_locator(lo, hi, nbins, name, minor.ndivs))


def _even_grid(lo, hi, max_ticks):
    """Return (start, stop, tick step) of an even tick grid around [lo, hi], or None.

    Grid steps go from coarse to fine; a grid may widen the span by at most
    _MAX_GROW. A tick on every grid line is tried first; failing that, ticks go on
    every k-th line, k a divisor of the interval count, so the ticks stay even and
    both limits keep one. A grid qualifies with 3 to ``max_ticks`` ticks.
    """
    span = hi - lo
    top = math.floor(math.log10(span)) + 1
    grids = []
    for exp in range(top, top - 4, -1):
        for mant in (5, 2.5, 2, 1):
            step = mant * 10.0**exp
            start = math.floor(lo / step + 1e-9) * step
            stop = math.ceil(hi / step - 1e-9) * step
            if stop - start <= (1 + _MAX_GROW) * span:
                grids.append((start, stop, step, round((stop - start) / step)))
    for every_line in (True, False):
        for start, stop, step, intervals in grids:
            for k in [1] if every_line else range(2, intervals + 1):
                if intervals % k == 0 and 3 <= intervals // k + 1 <= max_ticks:
                    return start, stop, k * step
    return None


def _data_range(ax, name):
    """Return (lo, hi, smallest positive value) of the data on all axes sharing ``name``."""
    lims = [a.dataLim for a in getattr(ax, f"get_shared_{name}_axes")().get_siblings(ax)]
    lo = min(getattr(b, f"interval{name}")[0] for b in lims)
    hi = max(getattr(b, f"interval{name}")[1] for b in lims)
    return lo, hi, min(getattr(b, f"minpos{name}") for b in lims)


def _has_marker(line):
    return line.get_visible() and line.get_marker() not in (None, "None", "none", " ", "")


def _unclip_markers(ax):
    """Draw whole the markers of a series that lies inside the axes, also on its edges."""
    box = ax.bbox.padded(0.5)
    for artist in ax.get_lines() + [c for c in ax.collections if isinstance(c, PathCollection)]:
        if isinstance(artist, PathCollection):
            pts = artist.get_offset_transform().transform(artist.get_offsets())
        elif _has_marker(artist):
            pts = artist.get_transform().transform(artist.get_xydata())
        else:
            continue
        pts = pts[np.isfinite(pts).all(axis=1)]
        inside = (pts >= [box.x0, box.y0]) & (pts <= [box.x1, box.y1])
        if artist.get_clip_on() and artist.get_clip_path() is None and len(pts) and inside.all():
            artist.set_clip_on(False)


def _set_lim(ax, name, lo, hi):
    """Set the limits of an axis and keep its direction."""
    if getattr(ax, f"{name}axis").get_inverted():
        lo, hi = hi, lo
    getattr(ax, f"set_{name}lim")(lo, hi)


def round_limits(ax, axis="both"):
    """Set axis limits on an even tick grid just outside the data range.

    The tick step is the coarsest of 1, 2, 2.5 and 5 times a power of ten whose
    grid widens the data span by at most a tenth and fits the axis length; the
    axis then keeps that step, so both limits carry a tick. Logarithmic axes go
    to whole decades. When no grid fits, the limits are set to the data range,
    for :func:`label_ends` to label. The data range covers every axes that shares
    the axis, and an inverted axis stays inverted. Axes with dates, categories or
    other units are left alone.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
    axis : {"both", "x", "y"}

    Raises
    ------
    ValueError
        If ``axis`` is not one of the three names.
    """
    if axis not in ("both", "x", "y"):
        raise ValueError(f"axis must be 'both', 'x' or 'y', got {axis!r}")
    for name in ("x", "y"):
        if axis not in ("both", name):
            continue
        ax_ = getattr(ax, f"{name}axis")
        lo, hi, minpos = _data_range(ax, name)
        if getattr(ax, f"get_{name}scale")() == "log":
            lo = lo if lo > 0 else minpos
        if not (np.isfinite(lo) and np.isfinite(hi)) or lo >= hi or ax_.have_units():
            continue
        if not isinstance(ax_.get_major_locator(), (MaxNLocator, MultipleLocator, LogLocator)):
            continue
        if getattr(ax, f"get_{name}scale")() == "log":
            lo, hi, _ = _round_limits(lo, hi, log=True)
            _set_lim(ax, name, lo, hi)
            continue
        grid = _even_grid(lo, hi, max(3, ax_.get_tick_space()))
        if grid is None:
            _set_lim(ax, name, lo, hi)
            continue
        start, stop, step = grid
        _set_lim(ax, name, start, stop)
        if abs(start / step - round(start / step)) < 1e-9:
            ax_.set_major_locator(MultipleLocator(step))
        else:
            n = round((stop - start) / step)
            ax_.set_major_locator(FixedLocator(start + step * np.arange(n + 1)))


def _at_ends(axis, values):
    """Return whether one of ``values`` lies on the lower and on the upper end of the axis."""
    lo, hi = sorted(axis.get_view_interval())
    v = np.asarray(list(values), dtype=float)
    if axis.get_scale() == "log":  # compare in decades
        v, lo, hi = np.log10(v[v > 0]), math.log10(lo), math.log10(hi)
    tol = _END_TOL * (hi - lo)
    return tuple(bool(np.any(np.abs(v - end) <= tol)) for end in (lo, hi))


def _ends_on_ticks(ax, name):
    axis = getattr(ax, f"{name}axis")
    return all(_at_ends(axis, axis.get_major_locator()()))


def _snap_to_ticks(ax, name):
    """Move each limit onto a tick when it lies within _SNAP of the span from one."""
    axis = getattr(ax, f"{name}axis")
    lims = np.asarray(getattr(ax, f"get_{name}lim")(), dtype=float)
    ticks = np.asarray(axis.get_major_locator()(), dtype=float)
    if axis.get_scale() == "log":  # distances in decades
        lims, ticks = np.log10(lims), np.log10(ticks[ticks > 0])
    span = abs(lims[1] - lims[0])
    new = list(getattr(ax, f"get_{name}lim")())
    for i, v in enumerate(lims):
        near = ticks[np.argmin(np.abs(ticks - v))]
        if abs(near - v) <= _SNAP * span:
            new[i] = 10.0**near if axis.get_scale() == "log" else near
    getattr(ax, f"set_{name}lim")(*new)


def _has_image(ax):
    return bool(ax.images) or any(
        type(c).__name__ in ("QuadMesh", "PolyQuadMesh") or getattr(c, "filled", False)
        for c in ax.collections
    )


def _default_ticks(axis):
    """True when an axis has numbers and the tick locator and formatter of matplotlib."""
    locator, formatter = axis.get_major_locator(), axis.get_major_formatter()
    return (
        not axis.have_units()
        and type(locator) in (AutoLocator, LogLocator)
        and isinstance(formatter, (ScalarFormatter, LogFormatter))
    )


def _all_axes(fig):
    """Every axes of a figure, with inset and secondary axes after their parent."""
    out = []
    for ax in fig.axes:
        out.append(ax)
        out += _all_axes_below(ax)
    return out


def _all_axes_below(ax):
    out = []
    for child in ax.child_axes:
        out.append(child)
        out += _all_axes_below(child)
    return out


def _secondary(ax):
    # A secondary axis takes its limits from its parent; only its labels are checked.
    return type(ax).__name__ == "SecondaryAxis"


def _save_dpi(fig, dpi):
    """The resolution ``savefig`` lays the figure out at, picked as ``savefig`` does."""
    dpi = mpl.rcParams["savefig.dpi"] if dpi is None else dpi
    return getattr(fig, "_original_dpi", fig.dpi) if dpi == "figure" else dpi


@contextmanager
def _at_dpi(fig, dpi):
    """Lay the figure out at the save resolution; text does not scale exactly with it."""
    old, manager = fig.dpi, fig.canvas.manager
    fig.canvas.manager = None  # as savefig does, so a window is not resized
    try:
        fig.dpi = _save_dpi(fig, dpi)
        yield
    finally:
        fig.dpi = old
        fig.canvas.manager = manager


def finish(fig, *, dpi=None):
    """Apply the layout rules to a figure and report what is still wrong.

    Axes with automatic limits get an even tick grid just outside their data
    (:func:`round_limits`), except axes that hold an image, a mesh or filled
    contours, whose limits stay at the data or snap to a tick within 2 % of the
    span. Axes whose ends are then not on a tick get labelled ends, and colour
    bars made with ``Figure.colorbar`` whose ends carry no tick get their end
    values as ticks. Markers of a series that lies inside its axes are drawn
    whole, so a point on an axis limit is not cut in half.
    Call it once, after the last change to the figure: the axes it changes no
    longer have the default ticks, so a second call leaves them alone. Inset
    axes count as axes. Only axes with the tick locator and formatter of
    matplotlib change: an axis with ticks set by hand, or with dates, categories
    or other units, keeps them. Polar, 3D and secondary axes and axes without
    visible axis lines are left alone.

    Parameters
    ----------
    fig : matplotlib.figure.Figure
    dpi : float or "figure", optional
        The resolution the figure is saved at, as passed to ``savefig``;
        defaults to ``rcParams["savefig.dpi"]``. See :func:`check_figure`.

    Returns
    -------
    list of str
        The problems :func:`check_figure` finds afterwards; empty when the
        figure follows the rules.
    """
    plain, bars, kept = [], [], []
    for ax in _all_axes(fig):
        cb = getattr(ax, "_colorbar", None)
        if cb is not None:
            long = cb.ax.yaxis if cb.orientation == "vertical" else cb.ax.xaxis
            if not getattr(cb, "_fwl_ends", False) and _default_ticks(long):
                bars.append(cb)
            continue
        if isinstance(ax, PolarAxes) or ax.name == "3d" or not ax.axison or _secondary(ax):
            continue
        kept.append(ax)
        image = _has_image(ax)
        for name in ("x", "y"):
            if not _default_ticks(getattr(ax, f"{name}axis")):
                continue
            plain.append((ax, name))
            if not getattr(ax, f"get_autoscale{name}_on")():
                continue
            if image:
                _snap_to_ticks(ax, name)
            else:
                round_limits(ax, name)
    # Tick locators settle only once the figure is laid out, and the axis length
    # they use changes a little with the resolution: decide at the save one.
    with _at_dpi(fig, dpi):
        fig.draw_without_rendering()
        for ax, name in plain:
            if not _ends_on_ticks(ax, name):
                label_ends(ax, name)
        for cb in bars:
            axis = cb.ax.yaxis if cb.orientation == "vertical" else cb.ax.xaxis
            if not _ends_on_ticks(cb.ax, axis.axis_name):
                lo, hi = sorted(axis.get_view_interval())
                cb.set_ticks(_end_ticks(lo, hi, log=axis.get_scale() == "log"))
                cb.formatter = FuncFormatter(_end_label)
            cb._fwl_ends = True
    for ax in kept:
        _unclip_markers(ax)
    return check_figure(fig, dpi=dpi)


# Checks


def _describe(artist):
    if isinstance(artist, Legend):
        return "legend"
    if _bar_outline(artist):
        return "colour bar"
    if hasattr(artist, "get_text"):
        return f"text {artist.get_text()!r}"
    label = artist.get_label()
    name = type(artist).__name__
    return f"{name} {label!r}" if label and not label.startswith("_") else name


def _shrunk(bbox):
    s = _SLACK_PX
    return Bbox.from_extents(bbox.x0 + s, bbox.y0 + s, bbox.x1 - s, bbox.y1 - s)


def _visible_ticklabels(axis):
    lo, hi = sorted(axis.get_view_interval())
    tol = (hi - lo) * 1e-9
    out = []
    for tick in axis.get_major_ticks():
        if not lo - tol <= tick.get_loc() <= hi + tol:
            continue
        for label in (tick.label1, tick.label2):
            if label.get_visible() and label.get_text():
                out.append(label)
    return out


def _figures(fig):
    """The figure and its subfigures, at every depth."""
    out = [fig]
    for sub in fig.subfigs:
        out += _figures(sub)
    return out


def _texts(fig):
    """Every visible text box of the figure, legends as one box each."""
    items = []
    for f in _figures(fig):
        items += [t for t in f.texts if t.get_visible() and t.get_text()]
        items += [legend for legend in f.legends if legend.get_visible()]
    for ax in _all_axes(fig):
        if not ax.get_visible():
            continue
        if ax.axison:
            for axis in (ax.xaxis, ax.yaxis):
                items += _visible_ticklabels(axis)
                for text in (axis.label, axis.offsetText):
                    if text.get_visible() and text.get_text():
                        items.append(text)
        for title in (ax.title, ax._left_title, ax._right_title):
            if title.get_visible() and title.get_text():
                items.append(title)
        items += [t for t in ax.texts if t.get_visible() and t.get_text()]
        legend = ax.get_legend()
        if legend is not None and legend.get_visible():
            items.append(legend)
    return items


def _bar_outline(artist):
    cb = getattr(getattr(artist, "axes", None), "_colorbar", None)
    return cb is not None and artist is cb.outline


def _obstacles(fig):
    """Data lines, markers, error bars, axis lines and colour bars, in display coordinates.

    Each entry is (artist, path, points, marker radius, filled); a filled path
    also hits a box that lies wholly inside it.
    """
    out = []
    for ax in _all_axes(fig):
        if not ax.get_visible():
            continue
        for line in ax.get_lines():
            if not line.get_visible():
                continue
            path = line.get_transform().transform_path(line.get_path())
            drawn = line.get_linestyle() not in ("None", "none", " ", "")
            marker = line.get_marker() not in (None, "None", "none", " ", "")
            radius = line.get_markersize() * fig.dpi / 72 / 2 if marker else 0
            out.append(
                (line, path if drawn else None, path.vertices if marker else None, radius, False)
            )
        for coll in ax.collections:
            if not coll.get_visible():
                continue
            if isinstance(coll, LineCollection):
                tr = coll.get_transform()
                for path in coll.get_paths():
                    out.append((coll, tr.transform_path(path), None, 0, False))
            elif isinstance(coll, PathCollection) and len(coll.get_offsets()):
                pts = coll.get_offset_transform().transform(coll.get_offsets())
                sizes = coll.get_sizes()
                radius = math.sqrt(sizes.max()) * fig.dpi / 72 / 2 if len(sizes) else 0
                out.append((coll, None, pts, radius, False))
        cb = getattr(ax, "_colorbar", None)
        if cb is not None:
            # The outline covers the bar and its extend triangles, also when hidden.
            path = cb.outline.get_transform().transform_path(cb.outline.get_path())
            out.append((cb.outline, path, None, 0, True))
        if ax.axison:
            for spine in ax.spines.values():
                if spine.get_visible() and not _bar_outline(spine):
                    path = spine.get_transform().transform_path(spine.get_path())
                    out.append((spine, path, None, 0, False))
    return out


def _clip(box, artist):
    """Limit a text box to the region where a clipped artist is drawn."""
    clip = artist.get_clip_box() if artist.get_clip_on() else None
    if clip is None:
        return box
    if not box.overlaps(clip):
        return None
    return Bbox.intersection(box, clip)


def _hits(bbox, path, points, radius, filled):
    if bbox is None:
        return False
    if path is not None and path.intersects_bbox(bbox, filled=filled):
        return True
    if points is not None and len(points):
        p = np.asarray(points)
        inside = (
            (p[:, 0] >= bbox.x0 - radius)
            & (p[:, 0] <= bbox.x1 + radius)
            & (p[:, 1] >= bbox.y0 - radius)
            & (p[:, 1] <= bbox.y1 + radius)
        )
        return bool(inside.any())
    return False


def _extent(item, renderer):
    # The box of an annotation's text alone: its arrow points at data on purpose.
    if isinstance(item, Annotation):
        return Text.get_window_extent(item, renderer)
    return item.get_window_extent(renderer)


def _covered(item, box, parent):
    """Return the inset under a text and the axes it covers, or (None, ()).

    Only an inset whose background is drawn and opaque hides the data of the
    axes below it; text that runs past the inset lies on the data around it.
    """
    inset = getattr(item, "axes", None)
    if inset not in parent or not (inset.axison and inset.get_frame_on()):
        return None, ()
    patch = inset.patch
    if not patch.get_visible() or patch.get_facecolor()[3] < 1:
        return None, ()
    if not (inset.bbox.contains(*box.p0) and inset.bbox.contains(*box.p1)):
        return None, ()
    below, above = [], parent[inset]
    while above is not None:
        below.append(above)
        above = parent.get(above)
    return inset, below


def _collisions(fig, renderer):
    problems = []
    texts = _texts(fig)
    boxes = [_shrunk(_extent(t, renderer)) for t in texts]
    for i, (a, ba) in enumerate(zip(texts, boxes, strict=True)):
        for b, bb in zip(texts[i + 1 :], boxes[i + 1 :], strict=True):
            if ba.overlaps(bb):
                problems.append(f"{_describe(a)} overlaps {_describe(b)}")
    obstacles = _obstacles(fig)
    parent = {child: ax for ax in _all_axes(fig) for child in ax.child_axes}
    for item, box in zip(texts, boxes, strict=True):
        inset, below = _covered(item, box, parent)
        for artist, path, points, radius, filled in obstacles:
            owner = getattr(artist, "axes", None)
            if owner in below and artist.get_zorder() < inset.get_zorder():
                continue
            if _hits(_clip(box, artist), path, points, radius, filled):
                problems.append(f"{_describe(item)} overlaps {_describe(artist)}")
    return problems


def _unlabelled_ends(fig):
    problems = []
    for n, ax in enumerate(_all_axes(fig)):
        if not (ax.get_visible() and ax.axison) or isinstance(ax, PolarAxes) or ax.name == "3d":
            continue
        if _secondary(ax):
            continue
        for name, axis in (("x", ax.xaxis), ("y", ax.yaxis)):
            if axis.have_units() or not _visible_ticklabels(axis):
                continue  # dates and categories, or tick labels hidden on purpose
            shown = {
                float(tick.get_loc())
                for tick in axis.get_major_ticks()
                if (tick.label1.get_visible() and tick.label1.get_text())
                or (tick.label2.get_visible() and tick.label2.get_text())
            }
            ends = zip(
                ("lower", "upper"),
                sorted(axis.get_view_interval()),
                _at_ends(axis, shown),
                strict=True,
            )
            for end, value, labelled in ends:
                if not labelled:
                    problems.append(
                        f"axes {n}: {name} axis {end} end {value:.6g} has no tick label"
                    )
    return problems


def check_figure(fig, *, dpi=None):
    """List the layout problems of a figure.

    The figure is laid out at the resolution it is saved at, as ``savefig``
    does, since a layout engine places text a little differently at another
    resolution. Text on a colour bar counts as text on data.

    Parameters
    ----------
    fig : matplotlib.figure.Figure
    dpi : float or "figure", optional
        The resolution the figure is saved at, as passed to ``savefig``;
        defaults to ``rcParams["savefig.dpi"]``. From matplotlib 3.11, PDF, SVG
        and PostScript files are laid out at it too; before, with their own
        text sizes, so text in them can sit a few tenths of a point away.

    Returns
    -------
    list of str
        One line per problem: text, tick labels or a legend that overlap a data
        line, a marker, an error bar, an axis line, a colour bar or other text,
        and axis or colour-bar ends without a tick label. Empty when the figure
        follows the rules. Rotated text is tested by its axis-aligned bounding
        box, which is larger than the glyphs, so rotated labels need clear space
        around them. Filled areas and images other than colour bars are not
        obstacles, an annotation is tested by its text, not its arrow, and text
        on an opaque inset is not tested against the data the inset covers.
        Axes are numbered in the order of ``fig.axes``, each followed by its
        inset and secondary axes. Polar, 3D and secondary axes, and axes with
        dates, categories or other units, are not tested for labelled ends.
    """
    with _at_dpi(fig, dpi):
        fig.draw_without_rendering()
        get_renderer = getattr(fig.canvas, "get_renderer", None)
        if get_renderer is None:  # canvases other than Agg, such as PDF or a bare Figure
            renderer = RendererAgg(fig.bbox.width, fig.bbox.height, fig.dpi)
        else:
            renderer = get_renderer()
        return _collisions(fig, renderer) + _unlabelled_ends(fig)
