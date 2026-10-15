"""Layout rules: the collision checker, labelled axis ends and colour bars."""

import runpy
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pytest  # noqa: E402

import fwl_mpl  # noqa: E402
from fwl_mpl import layout  # noqa: E402

SPECIMEN = Path(__file__).resolve().parents[1] / "examples" / "specimen.py"


@pytest.fixture(autouse=True)
def _style():
    fwl_mpl.use()
    yield
    plt.close("all")


def _clean_axes():
    fig, ax = plt.subplots()
    ax.plot([0, 10], [0, 10])
    ax.set(xlim=(0, 10), ylim=(0, 10))
    return fig, ax


def _collisions(fig):
    return [p for p in fwl_mpl.check_figure(fig) if "overlaps" in p]


# Collision checker


def test_clean_figure_has_no_problems():
    fig, ax = _clean_axes()
    ax.text(8, 1, "clear")
    assert fwl_mpl.check_figure(fig) == []


def test_text_on_a_line_is_reported():
    fig, ax = _clean_axes()
    ax.text(5, 5, "on the line", ha="center", va="center")
    assert _collisions(fig) == ["text 'on the line' overlaps Line2D"]


def test_legend_on_a_line_is_reported_and_names_the_line():
    fig, ax = plt.subplots()
    ax.plot([0, 10], [10, 0], label="falling")
    ax.set(xlim=(0, 10), ylim=(0, 10))
    ax.legend(loc="center")
    assert _collisions(fig) == ["legend overlaps Line2D 'falling'"]


def test_overlapping_texts_are_reported():
    fig, ax = _clean_axes()
    ax.text(8, 2, "first")
    ax.text(8.1, 2.05, "second")
    assert "text 'first' overlaps text 'second'" in _collisions(fig)


def test_text_across_an_axis_line_is_reported():
    fig, ax = _clean_axes()
    ax.text(5, 0, "on the axis", ha="center", va="center")
    assert any("overlaps Spine" in p for p in _collisions(fig))


def test_marker_scatter_point_and_error_bar_under_text_are_reported():
    fig, ax = plt.subplots()
    ax.set(xlim=(0, 10), ylim=(0, 10))
    ax.plot([2], [8], "o", label="marker")
    ax.scatter([5], [8], label="points")
    ax.errorbar([8], [5], yerr=[3], fmt="none")
    ax.text(2, 8, "m", ha="center", va="center")
    ax.text(5, 8, "s", ha="center", va="center")
    ax.text(8, 6, "e", ha="center", va="center")
    found = _collisions(fig)
    assert "text 'm' overlaps Line2D 'marker'" in found
    assert "text 's' overlaps PathCollection 'points'" in found
    assert "text 'e' overlaps LineCollection" in found


def test_text_just_beside_a_line_is_not_reported():
    fig, ax = _clean_axes()
    ax.text(7, 3, "below the line", ha="center", va="center")
    assert _collisions(fig) == []


def test_figure_legend_and_hidden_text_are_handled():
    fig, ax = _clean_axes()
    ax.text(5, 5, "hidden").set_visible(False)
    fig.text(0.5, 0.99, "figure title", ha="center", va="top")
    assert _collisions(fig) == []


# Labelled ends


def test_hand_set_limits_off_the_ticks_are_reported():
    fig, ax = _clean_axes()
    ax.set_xlim(0, 8.2)
    assert fwl_mpl.check_figure(fig) == ["axes 0: x axis upper end 8.2 has no tick label"]


def test_label_ends_puts_labels_on_both_limits():
    fig, ax = _clean_axes()
    ax.set_xlim(0.3, 8.2)
    fwl_mpl.label_ends(ax, "x")
    fig.draw_without_rendering()
    labels = [t.get_text() for t in ax.get_xticklabels()]
    assert (labels[0], labels[-1]) == ("0.3", "8.2")
    assert fwl_mpl.check_figure(fig) == []


def test_label_ends_drops_an_inner_tick_that_crowds_an_end():
    ticks = layout._end_ticks(0, 4.5)
    assert list(ticks) == [0, 1, 2, 3, 4.5]


def test_end_labels_use_the_typographic_minus():
    assert layout._end_label(-120) == "\N{MINUS SIGN}120"
    with matplotlib.rc_context({"axes.unicode_minus": False}):
        assert layout._end_label(-120) == "-120"


def test_hidden_tick_labels_are_not_reported():
    fig, ax = _clean_axes()
    ax.set_xlim(0, 8.2)
    ax.tick_params(labelbottom=False)
    assert fwl_mpl.check_figure(fig) == []


def test_round_limits_moves_limits_to_the_ticks_outside_the_data():
    fig, ax = plt.subplots()
    ax.plot([0.5, 9.7], [3, 700])
    ax.set_yscale("log")
    fwl_mpl.round_limits(ax)
    assert ax.get_xlim() == (0, 10)
    assert ax.get_ylim() == pytest.approx((1, 1000))


def test_round_limits_takes_a_finer_step_rather_than_widening_much():
    fig, ax = plt.subplots()
    ax.plot([0, 8], [0, 1])
    fwl_mpl.round_limits(ax, "x")  # a step of 5, 0 to 10, would widen by 25 %
    assert ax.get_xlim() == (0, 8)
    ticks = [v for v in ax.xaxis.get_major_locator()() if 0 <= v <= 8]
    assert ticks == pytest.approx([0, 2, 4, 6, 8])


@pytest.mark.parametrize(
    ("lo", "hi", "max_ticks", "grid"),
    [
        (310, 1730, 7, (250, 1750, 250)),
        (310, 1730, 4, (250, 1750, 500)),
        (0, 8, 9, (0, 8, 2)),
        (0.5, 9.7, 9, (0, 10, 5)),
        (0.0123, 0.0384, 15, (0.012, 0.04, 0.002)),
        (0.0123, 0.0384, 9, (0.012, 0.04, 0.004)),
    ],
)
def test_even_grid_choice(lo, hi, max_ticks, grid):
    assert layout._even_grid(lo, hi, max_ticks) == pytest.approx(grid)


def test_even_grid_returns_none_when_no_grid_fits():
    assert layout._even_grid(310, 1730, 2) is None


def test_round_limits_offset_grid_keeps_ticks_on_both_limits(monkeypatch):
    fig, ax = plt.subplots()
    ax.plot([0, 1], [310, 1730])
    monkeypatch.setattr(ax.yaxis, "get_tick_space", lambda: 4)
    fwl_mpl.round_limits(ax, "y")
    assert ax.get_ylim() == (250, 1750)
    assert ax.yaxis.get_major_locator()() == pytest.approx([250, 750, 1250, 1750])


def test_round_limits_falls_back_to_the_data_range(monkeypatch):
    fig, ax = plt.subplots()
    ax.plot([0, 1], [310, 1730])
    monkeypatch.setattr(layout, "_even_grid", lambda lo, hi, n: None)
    fwl_mpl.round_limits(ax, "y")
    assert ax.get_ylim() == (310, 1730)
    assert fwl_mpl.finish(fig) == []


def test_round_limits_leaves_date_axes_alone():
    import datetime as dt

    fig, ax = plt.subplots()
    ax.plot([dt.date(2026, 1, 1), dt.date(2026, 3, 1)], [0, 1])
    before = ax.get_xlim()
    fwl_mpl.round_limits(ax, "x")
    assert ax.get_xlim() == before


def test_round_limits_leaves_fixed_ticks_alone():
    fig, ax = plt.subplots()
    ax.plot([0.3, 7.7], [0, 1])
    ax.set_xticks([1, 4, 7])
    before = ax.get_xlim()
    fwl_mpl.round_limits(ax, "x")
    assert ax.get_xlim() == before


def test_round_limits_leaves_degenerate_data_alone():
    fig, ax = plt.subplots()
    ax.plot([2, 2], [-1, 5])
    ax.set_xlim(1, 3)
    ax.set_yscale("log")  # one positive value only
    before = ax.get_xlim(), ax.get_ylim()
    fwl_mpl.round_limits(ax)
    assert (ax.get_xlim(), ax.get_ylim()) == before


def test_round_limits_on_a_log_axis_starts_at_the_smallest_positive_value():
    fig, ax = plt.subplots()
    ax.plot([0, 1, 2], [0, 13, 870])
    ax.set_yscale("log")
    fwl_mpl.round_limits(ax, "y")
    assert ax.get_ylim() == pytest.approx((10, 1000))


@pytest.mark.parametrize("scale", ["linear", "log"])
def test_round_limits_keeps_an_inverted_axis_inverted(scale):
    limits = []
    for invert in (False, True):
        fig, ax = plt.subplots()
        ax.plot([1, 2, 3], [870, 130, 13])
        ax.set_yscale(scale)
        if invert:
            ax.invert_yaxis()
        fwl_mpl.round_limits(ax, "y")
        limits.append(ax.get_ylim())
    assert limits[0][0] < 13 and limits[0][1] > 870
    assert limits[1] == limits[0][::-1]


@pytest.mark.parametrize("twin", [False, True])
def test_finish_covers_the_data_of_every_axes_on_a_shared_axis(twin):
    if twin:
        fig, first = plt.subplots()
        second = first.twinx()
    else:
        fig, (first, second) = plt.subplots(2, sharex=True)
    first.plot([0, 3], [0, 1])
    second.plot([0, 9.6], [0, 1])
    assert fwl_mpl.finish(fig) == []
    assert first.get_xlim() == second.get_xlim() == (0, 10)


@pytest.mark.parametrize("func", [fwl_mpl.label_ends, fwl_mpl.round_limits])
def test_axis_name_is_checked(func):
    fig, ax = plt.subplots()
    with pytest.raises(ValueError, match="axis must be"):
        func(ax, "z")


# Colour bars


def test_colorbar_round_widens_to_tick_values_and_labels_both_ends():
    fig, ax = plt.subplots()
    im = ax.imshow(np.linspace(0, 0.384, 20).reshape(4, 5))
    cb = fwl_mpl.colorbar(im)
    assert (cb.norm.vmin, cb.norm.vmax) == pytest.approx((0, 0.4))
    assert cb.get_ticks()[[0, -1]] == pytest.approx([0, 0.4])
    assert not cb.outline.get_visible()
    assert not [p for p in fwl_mpl.check_figure(fig) if "axes 1" in p]


def test_colorbar_round_handles_a_log_norm():
    fig, ax = plt.subplots()
    im = ax.imshow(np.geomspace(3, 700, 20).reshape(4, 5), norm=matplotlib.colors.LogNorm())
    cb = fwl_mpl.colorbar(im)
    assert (cb.norm.vmin, cb.norm.vmax) == pytest.approx((1, 1000))


def test_colorbar_label_keeps_the_range_and_labels_the_exact_ends():
    fig, ax = plt.subplots()
    im = ax.imshow(np.linspace(-120, 120, 20).reshape(4, 5), cmap=fwl_mpl.cmap("diverging"))
    cb = fwl_mpl.colorbar(im, ends="label")
    assert (cb.norm.vmin, cb.norm.vmax) == (-120, 120)
    fig.draw_without_rendering()
    labels = [t.get_text() for t in cb.ax.get_yticklabels()]
    assert (labels[0], labels[-1]) == ("\N{MINUS SIGN}120", "120")


def test_colorbar_rejects_an_unknown_mode():
    fig, ax = plt.subplots()
    im = ax.imshow(np.eye(3))
    with pytest.raises(ValueError, match="ends must be"):
        fwl_mpl.colorbar(im, ends="exact")


def test_colorbar_takes_space_from_a_list_of_axes():
    fig, axs = plt.subplots(1, 2)
    im = axs[0].imshow(np.linspace(0, 0.384, 20).reshape(4, 5))
    cb = fwl_mpl.colorbar(im, ax=list(axs))
    assert cb.ax.figure is fig
    assert cb.get_ticks()[[0, -1]] == pytest.approx([0, 0.4])


def test_finish_keeps_colorbar_ticks_that_label_both_ends():
    fig, ax = plt.subplots()
    im = ax.imshow(np.linspace(0, 1, 20).reshape(4, 5))
    cb = fig.colorbar(im)
    cb.set_ticks([0, 0.5, 1])
    assert not [p for p in fwl_mpl.finish(fig) if "axes 1" in p]
    assert list(cb.get_ticks()) == [0, 0.5, 1]


def test_plain_colorbar_is_reported_and_finish_labels_it():
    fig, ax = plt.subplots()
    im = ax.imshow(np.linspace(0, 0.384, 20).reshape(4, 5))
    fig.colorbar(im)
    assert any("axes 1" in p for p in fwl_mpl.check_figure(fig))
    assert not [p for p in fwl_mpl.finish(fig) if "axes 1" in p]


# finish


def test_finish_rounds_autoscaled_axes_and_labels_hand_set_ones():
    fig, ax = plt.subplots()
    ax.plot(np.linspace(0.4, 9.6, 50), np.linspace(310, 1730, 50))
    ax.set_xlim(0, 9.6)
    assert fwl_mpl.finish(fig) == []
    assert ax.get_xlim() == (0, 9.6)
    lo, hi = ax.get_ylim()
    assert lo <= 310 and hi >= 1730 and fwl_mpl.check_figure(fig) == []


def test_finish_snaps_a_mesh_edge_to_the_nearby_tick():
    fig, ax = plt.subplots()
    x, y = np.meshgrid(np.linspace(0, 1, 101), np.linspace(0, 5, 101))
    ax.pcolormesh(x, y, x * y)
    assert ax.get_xlim()[0] < 0  # cell centres: the mesh overhangs by half a cell
    assert fwl_mpl.finish(fig) == []
    assert ax.get_xlim() == pytest.approx((0, 1))


def test_finish_leaves_polar_and_hidden_axes_alone():
    fig = plt.figure()
    pol = fig.add_subplot(1, 2, 1, projection="polar")
    pol.plot([0, 1], [0.2, 0.8])
    pol.set_xticklabels([])
    pol.set_yticklabels([])
    off = fig.add_subplot(1, 2, 2)
    off.axis("off")
    before = pol.get_ylim()
    assert fwl_mpl.finish(fig) == []
    assert pol.get_ylim() == before


@pytest.mark.parametrize("mode", fwl_mpl.MODES)
def test_specimen_follows_the_layout_rules(mode):
    specimen = runpy.run_path(str(SPECIMEN), run_name="specimen")["specimen"]
    fig = specimen(mode)
    assert fwl_mpl.finish(fig) == []


def test_titles_hidden_artists_and_hidden_axes_are_not_reported():
    fig, (ax, gone) = plt.subplots(1, 2)
    ax.set(xlim=(0, 10), ylim=(0, 10), title="A title")
    ax.plot([0, 10], [5, 5], label="level")
    ax.plot([0, 10], [8, 8]).pop().set_visible(False)
    ax.scatter([2], [2]).set_visible(False)
    ax.text(2, 8, "over hidden line")
    ax.text(2, 2, "over hidden points")
    gone.set_visible(False)
    gone.text(0.5, 0.5, "in a hidden axes")
    assert _collisions(fig) == []


def test_figure_legend_on_a_line_is_reported():
    fig, ax = plt.subplots()
    ax.set(xlim=(0, 10), ylim=(0, 10))
    (line,) = ax.plot([0, 10], [5, 5], label="level")
    fig.legend(handles=[line], loc="center")
    assert "legend overlaps Line2D 'level'" in _collisions(fig)


def test_finish_handles_a_mesh_axis_without_ticks():
    from matplotlib.ticker import NullLocator

    fig, ax = plt.subplots()
    ax.pcolormesh(np.arange(5), np.arange(4), np.ones((3, 4)))
    ax.xaxis.set_major_locator(NullLocator())
    assert fwl_mpl.finish(fig) == []
    assert ax.get_xlim() == (0, 4)


def test_finish_sizes_the_tick_grid_for_the_laid_out_axes():
    # Before layout the axes are taller; the grid must fit the final axes.
    fig, ax = plt.subplots(figsize=(1.6, 1.2))
    ax.plot(np.linspace(0.4, 9.6, 50), np.linspace(310, 1730, 50))
    ax.set_ylabel("A long label")
    assert fwl_mpl.finish(fig) == []
    ticks = [v for v in ax.get_yticks() if 250 <= v <= 1750]
    assert ticks == pytest.approx([250, 750, 1250, 1750])


@pytest.mark.parametrize("lim", [(0, 7.5), (0, 3000)])
def test_finish_labels_hand_set_ends_on_a_small_axes(lim):
    # Tick steps change when the layout shrinks the axes; the ends must still be labelled
    # and the labels must not run into each other.
    fig, ax = plt.subplots(figsize=(1.4, 1.2))
    ax.plot([0, 1], [0, 1])
    ax.set_xlim(*lim)
    ax.set_ylabel("Long label here")
    assert fwl_mpl.finish(fig) == []


def test_finish_keeps_category_and_date_ticks():
    import datetime as dt

    fig, (bars, dates) = plt.subplots(2, figsize=(6, 4))
    bars.bar(["a", "b", "c"], [1, 2, 3])
    dates.plot([dt.date(2026, 1, 1), dt.date(2026, 3, 1)], [0, 1])
    before = dates.xaxis.get_major_locator(), dates.xaxis.get_major_formatter()
    problems = fwl_mpl.finish(fig)
    assert [t.get_text() for t in bars.get_xticklabels()] == ["a", "b", "c"]
    assert (dates.xaxis.get_major_locator(), dates.xaxis.get_major_formatter()) == before
    assert not [p for p in problems if "x axis" in p]


def test_finish_keeps_ticks_set_by_hand_and_reports_their_ends():
    from matplotlib.ticker import MaxNLocator, PercentFormatter

    fig, (counts, share) = plt.subplots(1, 2)
    counts.plot(np.arange(8), np.arange(8))
    locator = MaxNLocator(integer=True)
    counts.xaxis.set_major_locator(locator)
    share.plot([0, 1], [0.13, 0.87])
    share.set_ylim(0.05, 0.95)
    formatter = PercentFormatter(1)
    share.yaxis.set_major_formatter(formatter)
    problems = fwl_mpl.finish(fig)
    assert counts.xaxis.get_major_locator() is locator
    assert share.yaxis.get_major_formatter() is formatter
    assert sum("axes 0: x axis" in p for p in problems) == 2
    assert sum("axes 1: y axis" in p for p in problems) == 2


def test_finish_twice_changes_nothing():
    fig, ax = plt.subplots()
    ax.plot([0.3, 7.7], [-2.2, 13.1])
    assert fwl_mpl.finish(fig) == []
    first = ax.get_xlim(), ax.get_ylim(), list(ax.get_xticks()), list(ax.get_yticks())
    assert fwl_mpl.finish(fig) == []
    assert (ax.get_xlim(), ax.get_ylim(), list(ax.get_xticks()), list(ax.get_yticks())) == first


def test_finish_leaves_3d_axes_alone():
    fig = plt.figure()
    ax = fig.add_subplot(projection="3d")
    t = np.linspace(0, 6, 50)
    ax.plot(np.cos(t), np.sin(t), t)
    before = ax.get_xlim(), ax.get_ylim(), ax.get_zlim()
    fwl_mpl.finish(fig)
    assert (ax.get_xlim(), ax.get_ylim(), ax.get_zlim()) == before


# Review cases: canvases, insets, log ends, markers, annotations, contours


@pytest.mark.parametrize("canvas", [None, "pdf"])
def test_check_works_without_an_agg_canvas(canvas):
    from matplotlib.backends.backend_pdf import FigureCanvasPdf
    from matplotlib.figure import Figure

    fig = Figure()
    if canvas == "pdf":
        FigureCanvasPdf(fig)
    ax = fig.add_subplot()
    ax.plot([0, 10], [0, 10])
    ax.set(xlim=(0, 10), ylim=(0, 10))
    ax.text(5, 5, "on the line", ha="center", va="center")
    assert fwl_mpl.finish(fig) == ["text 'on the line' overlaps Line2D"]


def test_finish_treats_an_inset_as_axes_and_leaves_a_secondary_axis_alone():
    fig, ax = plt.subplots()
    ax.plot([0, 10], [0, 1])
    ax.set_ylim(0, 10)  # the line stays below the inset
    inset = ax.inset_axes([0.1, 0.55, 0.35, 0.35])
    inset.plot([0.3, 7.7], [0, 1])
    secondary = ax.secondary_xaxis(
        "top", functions=(lambda x: 2 * x + 0.3, lambda x: (x - 0.3) / 2)
    )
    assert fwl_mpl.finish(fig) == []
    assert inset.get_xlim() == (0, 8)
    assert secondary.get_xlim() == pytest.approx((0.3, 20.3))  # follows the parent, 0 to 10
    assert type(secondary.xaxis.get_major_locator()).__name__ == "AutoLocator"
    inset.text(4, 0.5, "on the inset line", ha="center", va="center")
    assert _collisions(fig) == ["text 'on the inset line' overlaps Line2D"]


def test_label_ends_on_a_log_axis_puts_powers_of_ten_between_the_ends():
    fig, ax = plt.subplots()
    ax.plot([1, 2], [3, 700])
    ax.set_yscale("log")
    ax.set_ylim(3, 700)
    assert fwl_mpl.finish(fig) == []
    assert [t.get_text() for t in ax.get_yticklabels()] == ["3", "100", "700"]


def test_log_colorbar_with_labelled_ends_puts_powers_of_ten_between_them():
    fig, ax = plt.subplots()
    im = ax.imshow(np.geomspace(3, 700, 20).reshape(4, 5), norm=matplotlib.colors.LogNorm())
    cb = fwl_mpl.colorbar(im, ends="label")
    assert list(cb.get_ticks()) == pytest.approx([3, 100, 700])


def test_label_ends_puts_minor_ticks_on_the_step_of_the_inner_ticks():
    fig, ax = plt.subplots()
    ax.plot([0, 10], [0, 1])
    ax.set_xlim(0.3, 8.2)
    assert fwl_mpl.finish(fig) == []
    assert list(ax.get_xticks()) == pytest.approx([0.3, 2, 4, 6, 8.2])
    halves = np.arange(1, 17) * 0.5
    expected = halves[~np.isin(halves, [2, 4, 6])]  # minor ticks on a major tick are dropped
    minor = [v for v in ax.xaxis.get_minorticklocs() if 0.3 <= v <= 8.2]
    assert minor == pytest.approx(expected)


def test_end_labels_keep_six_significant_digits():
    assert [layout._end_label(v) for v in (12000, 0.123456)] == ["12000", "0.123456"]


def test_an_end_that_is_zero_but_for_rounding_error_is_labelled_0():
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    ax.set_ylim(0.1 + 0.2 - 0.3, 0.97)  # 5.55e-17
    assert fwl_mpl.finish(fig) == []
    assert ax.get_yticklabels()[0].get_text() == "0"


def test_finish_draws_markers_on_an_axis_limit_whole():
    fig, (ax, out) = plt.subplots(1, 2)
    (dots,) = ax.plot(np.arange(11), np.arange(11), "o")
    (line,) = ax.plot([0, 10], [5, 5])
    points = ax.scatter([0, 10], [3, 3])
    (beyond,) = out.plot(np.arange(11), np.arange(11), "o")
    out.set_xlim(0, 8)
    assert fwl_mpl.finish(fig) == []
    assert ax.get_xlim() == (0, 10)
    assert (dots.get_clip_on(), points.get_clip_on(), line.get_clip_on()) == (False, False, True)
    assert beyond.get_clip_on()  # points outside the limits stay clipped


def test_annotation_is_tested_by_its_text_and_not_its_arrow():
    fig, ax = _clean_axes()
    ax.annotate("peak", xy=(8, 4), xytext=(1, 9), arrowprops={"arrowstyle": "->"})
    assert _collisions(fig) == []
    ax.annotate("on it", xy=(8, 4), xytext=(5, 5), ha="center", va="center")
    assert _collisions(fig) == ["text 'on it' overlaps Line2D"]


def test_offset_text_is_checked():
    fig, ax = plt.subplots()
    ax.plot([0, 1], [1e6, 1e6 + 3])
    fig.draw_without_rendering()
    assert ax.yaxis.offsetText in layout._texts(fig)


def test_colorbar_keeps_ticks_and_format_given_and_needs_an_axes():
    fig, ax = plt.subplots()
    im = ax.imshow(np.linspace(0, 0.384, 20).reshape(4, 5))
    cb = fwl_mpl.colorbar(im, ends="label", ticks=[0, 0.2, 0.384], format="%.2f")
    fig.draw_without_rendering()
    assert [t.get_text() for t in cb.ax.get_yticklabels()] == ["0.00", "0.20", "0.38"]
    lone = matplotlib.cm.ScalarMappable(cmap=fwl_mpl.cmap("sequential"))
    with pytest.raises(ValueError, match="pass ax"):
        fwl_mpl.colorbar(lone)
    with pytest.raises(TypeError):
        fwl_mpl.colorbar(
            im, ax
        )  # ax is keyword-only; the second argument of Figure.colorbar is cax


def test_contour_colorbar_keeps_the_levels():
    fig, ax = plt.subplots()
    x = np.linspace(0, 1, 30)
    cs = ax.contourf(np.outer(x, x) * 7.3 + 0.2, levels=[0.2, 1.5, 3.1, 4.4, 6.0, 7.5])
    cb = fwl_mpl.colorbar(cs)
    assert (cs.norm.vmin, cs.norm.vmax) == (0.2, 7.5)
    assert cb.get_ticks()[[0, -1]] == pytest.approx([0.2, 7.5])


@pytest.mark.skipif(
    tuple(map(int, matplotlib.__version__.split(".")[:2])) < (3, 8),
    reason="contour sets are axes collections from matplotlib 3.8",
)
def test_finish_keeps_filled_contours_at_their_data():
    fig, ax = plt.subplots()
    ax.contourf(np.outer(np.arange(30), np.arange(30)))
    assert fwl_mpl.finish(fig) == []
    assert ax.get_xlim() == (0, 29)


def test_finish_puts_powers_of_ten_between_the_ends_of_a_plain_log_colorbar():
    fig, ax = plt.subplots()
    im = ax.imshow(np.geomspace(3, 700, 20).reshape(4, 5), norm=matplotlib.colors.LogNorm())
    cb = fig.colorbar(im)
    assert not [p for p in fwl_mpl.finish(fig) if "axes 1" in p]
    assert list(cb.get_ticks()) == pytest.approx([3, 100, 700])


def test_finish_leaves_an_axis_with_units_alone():
    import matplotlib.units as munits

    class Metres:
        def __init__(self, value):
            self.value = value

    class Converter(munits.ConversionInterface):
        @staticmethod
        def convert(value, unit, axis):
            return np.array([v.value for v in np.atleast_1d(value)], dtype=float)

        @staticmethod
        def axisinfo(unit, axis):
            return munits.AxisInfo(label="m")  # no locator: matplotlib's default ticks

        @staticmethod
        def default_units(x, axis):
            return "m"

    munits.registry[Metres] = Converter()
    try:
        fig, ax = plt.subplots()
        ax.plot([Metres(0.3), Metres(7.7)], [0, 1])
        before = ax.get_xlim()
        problems = fwl_mpl.finish(fig)
        assert ax.xaxis.have_units() and ax.get_xlim() == before
        assert type(ax.xaxis.get_major_locator()).__name__ == "AutoLocator"
        fwl_mpl.round_limits(ax, "x")
        assert ax.get_xlim() == before
        assert not [p for p in problems if "x axis" in p]
    finally:
        del munits.registry[Metres]


def test_text_and_legend_of_a_subfigure_are_checked():
    fig = plt.figure(figsize=(6, 3))
    left, _ = fig.subfigures(1, 2)
    ax = left.subplots()
    ax.set(xlim=(0, 10), ylim=(0, 10))
    (line,) = ax.plot([0, 10], [5, 5], label="level")
    left.text(2, 5, "on the line", va="center", transform=ax.transData)
    left.legend(handles=[line], loc="center")
    found = _collisions(fig)
    assert "text 'on the line' overlaps Line2D 'level'" in found
    assert "legend overlaps Line2D 'level'" in found


@pytest.mark.parametrize(("lo", "hi"), [(0.3, 0.7), (0.7, 1.1), (1.2, 1.6), (1.4, 1.8)])
def test_round_limits_of_a_range_whose_ends_are_inexact_ticks(lo, hi):
    # MaxNLocator gives 0.30000000000000004 for 0.3, just above the data.
    vmin, vmax, ticks = layout._round_limits(lo, hi)
    assert (vmin, vmax) == pytest.approx((lo, hi))  # both ends are tick values already
    assert ticks[[0, -1]] == pytest.approx([vmin, vmax])


def test_colorbar_for_a_mappable_without_data_spans_0_to_1():
    fig, ax = plt.subplots()
    lone = matplotlib.cm.ScalarMappable(cmap=fwl_mpl.cmap("sequential"))
    cb = fwl_mpl.colorbar(lone, ax=ax)
    assert lone.get_clim() == (0, 1)
    assert cb.get_ticks()[[0, -1]] == pytest.approx([0, 1])


def test_ends_of_a_log_axis_are_compared_in_decades():
    fig, ax = plt.subplots()
    ax.plot([1, 2], [3e-5, 5e3])
    ax.set(xlim=(1, 2), yscale="log", ylim=(2e-5, 1e4))
    # In linear units the tick at 1e-4 is within 1e-6 of the span from 2e-5.
    assert "axes 0: y axis lower end 2e-05 has no tick label" in fwl_mpl.check_figure(fig)
    assert fwl_mpl.finish(fig) == []


def test_minor_ticks_divide_a_step_of_2_5_into_5():
    locator = layout._minor_locator(0, 10, 4, "x")  # major step 2.5
    assert np.diff(locator.tick_values(0, 10)) == pytest.approx(0.5)


@pytest.mark.skipif("xtick.minor.ndivs" not in matplotlib.rcParams, reason="rc setting from 3.8")
def test_minor_ticks_follow_the_ndivs_setting():
    with matplotlib.rc_context({"xtick.minor.ndivs": 2}):
        locator = layout._minor_locator(0, 10, 4, "x")
    assert np.diff(locator.tick_values(0, 5)) == pytest.approx(1.25)


def test_a_log_mesh_snaps_in_decades():
    fig, ax = plt.subplots()
    x = np.geomspace(3, 700, 30)
    ax.pcolormesh(x, x, np.outer(x, x))
    ax.set(xscale="log", yscale="log")
    lo = ax.get_xlim()[0]
    fwl_mpl.finish(fig)
    assert ax.get_xlim()[0] == pytest.approx(lo)  # 2.7 is 0.43 decades from 1, not within 2 %


@pytest.mark.parametrize(("lo", "hi"), [(3e-5, 7e5), (3e-6, 7e6), (2, 7e10)])
def test_a_wide_log_colorbar_keeps_both_end_ticks(lo, hi):
    fig, ax = plt.subplots()
    im = ax.imshow(np.geomspace(lo, hi, 20).reshape(4, 5), norm=matplotlib.colors.LogNorm())
    cb = fwl_mpl.colorbar(im)
    assert cb.get_ticks()[[0, -1]] == pytest.approx(im.get_clim())
    assert not [p for p in fwl_mpl.finish(fig) if "axes 1" in p]


def test_text_on_an_opaque_inset_is_not_tested_against_the_data_it_covers():
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.plot([0, 10], [5, 5])  # runs behind the inset
    ax.set(xlim=(0, 10), ylim=(0, 10))
    inset = ax.inset_axes([0.15, 0.4, 0.55, 0.55])  # covers y 4 to 9.5
    inset.plot([0, 1], [0.9, 0.9])
    inset.set(xlim=(0, 1), ylim=(0, 1))
    on_hidden = {"transform": inset.transAxes, "va": "center"}
    inset.text(0.2, 1 / 5.5, "hidden", **on_hidden)
    inset.text(0.8, 1 / 5.5, "runs past the inset", **on_hidden)
    inset.text(0.5, 0.9, "on the inset line", transform=inset.transAxes, ha="center", va="center")
    names = ("hidden", "runs past", "inset line")
    found = sorted(p for p in _collisions(fig) if any(n in p for n in names))
    assert found == [
        "text 'on the inset line' overlaps Line2D",
        "text 'runs past the inset' overlaps Line2D",
    ]
    inset.patch.set_visible(False)
    assert any("'hidden'" in p for p in _collisions(fig))


def test_a_short_log_axis_has_no_minor_labels_after_labelling_its_ends():
    fig, ax = plt.subplots()
    ax.plot([1, 2], [2, 8])
    ax.set(yscale="log", ylim=(2, 8))
    assert fwl_mpl.finish(fig) == []
    fig.draw_without_rendering()
    assert [t.get_text() for t in ax.get_yticklabels()] == ["2", "8"]
    assert not [t.get_text() for t in ax.yaxis.get_minorticklabels() if t.get_text()]


def test_colorbar_with_cax_and_a_log_norm_without_limits():
    fig, ax = plt.subplots()
    cax = fig.add_axes([0.9, 0.1, 0.03, 0.8])
    free = matplotlib.cm.ScalarMappable(norm=matplotlib.colors.Normalize(0, 3.3))
    cb = fwl_mpl.colorbar(free, cax=cax)
    assert cb.ax is cax and cb.get_ticks()[[0, -1]] == pytest.approx([0, 4])
    unset = matplotlib.cm.ScalarMappable(norm=matplotlib.colors.LogNorm())
    with pytest.raises(ValueError, match="log norm"):
        fwl_mpl.colorbar(unset, ax=ax)


def test_plain_horizontal_colorbar_gets_its_ends():
    fig, ax = plt.subplots()
    im = ax.imshow(np.linspace(0, 0.384, 20).reshape(4, 5))
    cb = fig.colorbar(im, orientation="horizontal")
    assert not [p for p in fwl_mpl.finish(fig) if "axes 1" in p]
    assert cb.get_ticks()[[0, -1]] == pytest.approx([0, 0.384])


@pytest.mark.parametrize("kind", ["bar", "hist", "scatter", "errorbar", "fill_between", "step"])
def test_finish_on_common_plot_types(kind):
    fig, ax = plt.subplots()
    x = np.linspace(0.4, 9.6, 12)
    y = 3 + np.sin(x)
    {
        "bar": lambda: ax.bar(x, y, width=0.5),
        "hist": lambda: ax.hist(np.random.default_rng(1).normal(5, 2, 500), bins=15),
        "scatter": lambda: ax.scatter(x, y),
        "errorbar": lambda: ax.errorbar(x, y, yerr=0.4, fmt="o"),
        "fill_between": lambda: ax.fill_between(x, y - 1, y + 1),
        "step": lambda: ax.step(x, y),
    }[kind]()
    data = ax.dataLim
    assert fwl_mpl.finish(fig) == []
    (x0, x1), (y0, y1) = ax.get_xlim(), ax.get_ylim()
    assert x0 <= data.x0 and x1 >= data.x1 and y0 <= data.y0 and y1 >= data.y1


def test_set_ylim_bottom_labels_the_other_end_exactly():
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0.4, 9.6])
    ax.set_ylim(bottom=0)
    top = ax.get_ylim()[1]
    assert fwl_mpl.finish(fig) == []
    assert ax.get_yticks()[[0, -1]] == pytest.approx([0, top])


def test_markers_are_drawn_whole_on_an_axes_without_default_ticks():
    fig, ax = plt.subplots()
    (dots,) = ax.plot(["a", "b", "c"], [0, 5, 10], "o")
    ax.set(yticks=[0, 5, 10], ylim=(0, 10))
    assert fwl_mpl.finish(fig) == []
    assert not dots.get_clip_on()
