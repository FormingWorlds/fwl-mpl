"""Colour guarantees: hex format, contrast, and separation under colour-vision deficiency."""

import re
from itertools import combinations

import fwl_visual_language as fvl
import numpy as np
import pytest
from colorspacious import cspace_convert

import fwl_mpl

HEX = re.compile(r"^#[0-9A-F]{6}$")
CVD = [None] + [
    {"name": "sRGB1+CVD", "cvd_type": t, "severity": 100}
    for t in ("deuteranomaly", "protanomaly", "tritanomaly")
]
# Floors just under the measured minima (14.97 light, 11.00 dark); see the README.
MIN_DELTA_E = {"light": 14.9, "dark": 10.9}
MIN_OBSERVED_DELTA_E = 12.0
MIN_CONTRAST = {"light": 3.0, "dark": 4.5}


def rgb(h):
    return np.array([int(h[i : i + 2], 16) / 255 for i in (1, 3, 5)])


def contrast(a, b):
    """WCAG 2 contrast ratio of two hex colours."""

    def lum(h):
        c = rgb(h)
        lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
        return float(lin @ [0.2126, 0.7152, 0.0722])

    hi, lo = sorted([lum(a), lum(b)], reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def min_delta_e(hexes):
    """Smallest pairwise CAM02-UCS distance over normal vision and 3 CVD types."""
    cols = np.array([rgb(h) for h in hexes])
    worst = np.inf
    for cvd in CVD:
        sim = cols if cvd is None else np.clip(cspace_convert(cols, cvd, "sRGB1"), 0, 1)
        ucs = cspace_convert(sim, "sRGB1", "CAM02-UCS")
        for i, j in combinations(range(len(hexes)), 2):
            worst = min(worst, float(np.linalg.norm(ucs[i] - ucs[j])))
    return worst


def test_contrast_reference_values():
    # Known WCAG values: black/white 21:1, #767676 on white 4.54:1.
    assert contrast("#000000", "#FFFFFF") == pytest.approx(21.0)
    assert contrast("#767676", "#FFFFFF") == pytest.approx(4.54, abs=0.01)


def test_min_delta_e_detects_red_green_confusion():
    # Canary: a red/green pair is far apart in normal vision but not for deutans.
    assert min_delta_e(["#D62728", "#2CA02C"]) < 8


@pytest.mark.parametrize("mode", fwl_mpl.MODES)
def test_palette_names_and_format(mode):
    pal = fwl_mpl.PALETTE[mode]
    assert tuple(pal) == fwl_mpl.NAMES
    assert all(HEX.match(h) for h in pal.values())
    assert len(set(pal.values())) == 8


@pytest.mark.parametrize(("mode", "theme"), [("light", "paper"), ("dark", "dark")])
def test_colours_are_the_token_values(mode, theme):
    assert list(fwl_mpl.PALETTE[mode].items()) == fvl.palette(theme)
    r = fvl.roles(theme)
    s = fwl_mpl.SURFACES[mode]
    assert (s["background"], s["ink"], s["muted"], s["axis"], s["line"]) == (
        r["background"],
        r["heading"],
        r["muted"],
        r["axis"],
        r["line"],
    )
    assert fwl_mpl.COLORMAPS[mode]["sequential"] == "cmc.batlow"


def test_cycles_follow_names():
    assert fwl_mpl.CYCLE == [fwl_mpl.PALETTE["light"][n] for n in fwl_mpl.NAMES]
    assert fwl_mpl.CYCLE_DARK == [fwl_mpl.PALETTE["dark"][n] for n in fwl_mpl.NAMES]


@pytest.mark.parametrize("mode", fwl_mpl.MODES)
def test_palette_contrast_against_background(mode):
    bg = fwl_mpl.SURFACES[mode]["background"]
    for name, h in fwl_mpl.PALETTE[mode].items():
        assert contrast(h, bg) >= MIN_CONTRAST[mode], name


@pytest.mark.parametrize("mode", fwl_mpl.MODES)
def test_text_neutrals_are_readable(mode):
    s = fwl_mpl.SURFACES[mode]
    assert contrast(s["ink"], s["background"]) >= 7.0
    assert contrast(s["muted"], s["background"]) >= 4.5
    assert contrast(s["axis"], s["background"]) >= 4.5
    assert contrast(s["observed"], s["background"]) >= 4.5


@pytest.mark.parametrize("mode", fwl_mpl.MODES)
def test_observed_colour_separates_from_palette(mode):
    observed = fwl_mpl.SURFACES[mode]["observed"]
    for name, h in fwl_mpl.PALETTE[mode].items():
        assert min_delta_e([observed, h]) >= MIN_OBSERVED_DELTA_E, name


@pytest.mark.parametrize("mode", fwl_mpl.MODES)
def test_palette_separation_under_cvd(mode):
    assert min_delta_e(fwl_mpl.colors(mode=mode)) >= MIN_DELTA_E[mode]


@pytest.mark.parametrize("mode", fwl_mpl.MODES)
def test_no_pair_comes_closer_at_partial_severity_than_at_full_severity(mode):
    full = min_delta_e(fwl_mpl.colors(mode=mode))
    cols = np.array([rgb(h) for h in fwl_mpl.colors(mode=mode)])
    for kind in ("deuteranomaly", "protanomaly", "tritanomaly"):
        for severity in range(1, 101):
            cvd = {"name": "sRGB1+CVD", "cvd_type": kind, "severity": severity}
            sim = np.clip(cspace_convert(cols, cvd, "sRGB1"), 0, 1)
            ucs = cspace_convert(sim, "sRGB1", "CAM02-UCS")
            worst = min(
                float(np.linalg.norm(ucs[i] - ucs[j])) for i, j in combinations(range(8), 2)
            )
            assert worst >= full - 1e-9, (kind, severity, worst)


# Okabe-Ito, 7 colours without black.
OKABE_ITO = ["#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00", "#CC79A7"]


@pytest.mark.parametrize(
    ("hexes", "expected"),
    [
        (fwl_mpl.colors(mode="light"), 15.0),
        (fwl_mpl.colors(mode="dark"), 11.0),
        (OKABE_ITO, 11.0),
    ],
    ids=["light", "dark", "okabe-ito"],
)
def test_readme_minimum_separation_numbers(hexes, expected):
    assert min_delta_e(hexes) == pytest.approx(expected, abs=0.05)


def test_tritan_confusion_canary():
    # Yellow and pink are close for tritans and far apart for normal vision.
    pair = ["#F0E442", "#FF9EB5"]
    tritan = {"name": "sRGB1+CVD", "cvd_type": "tritanomaly", "severity": 100}
    cols = np.array([rgb(h) for h in pair])
    plain = np.linalg.norm(np.diff(cspace_convert(cols, "sRGB1", "CAM02-UCS"), axis=0))
    sim = np.clip(cspace_convert(cols, tritan, "sRGB1"), 0, 1)
    seen = np.linalg.norm(np.diff(cspace_convert(sim, "sRGB1", "CAM02-UCS"), axis=0))
    assert seen < plain
