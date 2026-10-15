"""Render the style specimen in light and dark mode.

Run ``python examples/specimen.py [output_dir]``; the default output directory is
``examples/output``. The data are synthetic and only show the style.
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from colorspacious import cspace_convert  # noqa: E402

import fwl_mpl  # noqa: E402


def specimen(mode):
    """Build the 6-panel specimen figure for one mode.

    Parameters
    ----------
    mode : {"light", "dark"}

    Returns
    -------
    matplotlib.figure.Figure
    """
    fwl_mpl.use(mode)
    surf = fwl_mpl.SURFACES[mode]
    cyc = fwl_mpl.colors(mode=mode)
    rng = np.random.default_rng(3)
    fig = plt.figure(figsize=(7.1, 4.6))
    axs = [fig.add_subplot(2, 3, i) for i in (1, 2, 3, 5, 6)]
    ax_pol = fig.add_subplot(2, 3, 4, projection="polar")

    # a: 8 series
    ax = axs[0]
    t = np.linspace(0, 8, 300)
    for r in (10, 20, 30, 40, 50, 60, 70, 80):
        tau = 0.6 + 0.04 * r
        peak = (1500 - 8 * (80 - r)) * (1 - np.exp(-r / 25))
        ax.plot(t, 300 + peak * (t / tau) * np.exp(1 - t / tau), label=f"{r} km")
    ax.set(xlabel=r"Time after CAI, $t$ (Myr)", ylabel=r"Peak temperature, $T_\mathrm{max}$ (K)")
    ax.set_ylim(0, 3000)  # headroom above the curves for the legend
    ax.legend(
        ncol=2,
        loc="upper right",
        fontsize=7,
        handlelength=1.0,
        columnspacing=0.8,
        labelspacing=0.25,
    )

    # b: models with uncertainty bands and observed points
    ax = axs[1]
    m = np.linspace(0.5, 10, 100)
    for k, (f, name) in enumerate([(1.0, "Earth-like"), (0.82, "Fe-rich"), (1.25, "H$_2$O 30%")]):
        r = f * m**0.27
        ax.plot(m, r, color=cyc[k], label=name)
        ax.fill_between(m, 0.97 * r, 1.03 * r, color=cyc[k], alpha=0.18, lw=0)
    mo = np.array([0.9, 1.6, 2.4, 4.1, 5.5, 7.3, 8.6])
    ro = mo**0.27 * (1 + rng.normal(0, 0.06, mo.size))
    ax.errorbar(
        mo,
        ro,
        yerr=0.06 * ro,
        xerr=0.08 * mo,
        fmt="o",
        color=surf["observed"],
        ms=3,
        elinewidth=0.7,
        label="Observed",
        zorder=5,
    )
    ax.set(
        xlabel=r"Mass, $M_\mathrm{p}$ ($M_\mathrm{Earth}$)",
        ylabel=r"Radius, $R_\mathrm{p}$ ($R_\mathrm{Earth}$)",
    )
    ax.set_ylim(0, 2.5)  # room below the curves for the legend
    ax.legend(loc="lower right", labelspacing=0.25)

    # c: sequential field
    ax = axs[2]
    x, y = np.meshgrid(np.linspace(0, 1, 200), np.linspace(0, 5, 200))
    phi = 0.2 * (1 - np.tanh((y - 1.5 - 2.5 * x**2) * 1.8))
    im = ax.pcolormesh(x, y, phi, cmap=fwl_mpl.cmap("sequential", mode), rasterized=True)
    fwl_mpl.colorbar(im, ax=ax, label=r"Porosity, $\varphi$")
    ax.set(xlabel=r"Normalised radius, $r/R$", ylabel=r"Time, $t$ (Myr)")

    # d: diverging field on a polar grid
    th, rr = np.meshgrid(np.linspace(0, 2 * np.pi, 240), np.linspace(0.3, 1, 120))
    dT = 120 * np.sin(3 * th) * np.sin(np.pi * (rr - 0.3) / 0.7)
    im = ax_pol.pcolormesh(
        th, rr, dT, cmap=fwl_mpl.cmap("diverging", mode), vmin=-120, vmax=120, rasterized=True
    )
    ax_pol.set_xticklabels([])
    ax_pol.set_yticklabels([])
    ax_pol.grid(False)
    fwl_mpl.colorbar(
        im,
        ax=ax_pol,
        ends="label",
        pad=0.08,
        shrink=0.85,
        label=r"Temperature anomaly, $\Delta T$ (K)",
    )

    # e: all 8 colours as stacked fills
    ax = axs[3]
    t = np.linspace(0, 4.5, 60)
    peaks = [(0.5, 1), (1.5, 2), (2.5, 1.5), (3.5, 3), (1, 4), (3, 1), (2, 6), (4, 2)]
    base = np.array([np.exp(-((t - mu) ** 2) / s) + 0.3 for mu, s in peaks])
    names = ["H$_2$O", "CO$_2$", "CO", "H$_2$", "N$_2$", "CH$_4$", "SO$_2$", "H$_2$S"]
    ax.stackplot(
        t, base / base.sum(0), labels=names, colors=cyc, lw=0.4, edgecolor=surf["background"]
    )
    ax.set(xlim=(0, 4.5), ylim=(0, 1), xlabel=r"Time, $t$ (Gyr)", ylabel=r"Mole fraction, $x_i$")
    ax.legend(loc="center left", bbox_to_anchor=(1.0, 0.5), handlelength=1, labelspacing=0.3)

    # f: palette under simulated colour-vision deficiency, and in greyscale
    ax = axs[4]
    rgb = np.array([[int(h[i : i + 2], 16) / 255 for i in (1, 3, 5)] for h in cyc])
    rows = {"normal": rgb}
    for short, typ in (
        ("deutan", "deuteranomaly"),
        ("protan", "protanomaly"),
        ("tritan", "tritanomaly"),
    ):
        cvd = {"name": "sRGB1+CVD", "cvd_type": typ, "severity": 100}
        rows[short] = np.clip(cspace_convert(rgb, cvd, "sRGB1"), 0, 1)
    rows["grey"] = np.repeat(cspace_convert(rgb, "sRGB1", "JCh")[:, :1] / 100, 3, 1)
    for j, (label, row) in enumerate(rows.items()):
        for i, c in enumerate(row):
            ax.add_patch(plt.Rectangle((i, -j), 0.92, 0.85, color=c, lw=0))
        ax.text(-0.15, -j + 0.42, label, ha="right", va="center", fontsize=6.5, color=surf["muted"])
    for i, name in enumerate(fwl_mpl.NAMES):
        ax.text(i + 0.46, 1.0, name, rotation=90, ha="center", va="bottom", fontsize=6.5)
    ax.set(xlim=(-1.6, 8.1), ylim=(-4.3, 2.8))
    ax.axis("off")

    for ax, label in zip([axs[0], axs[1], axs[2], ax_pol, axs[3], axs[4]], "abcdef", strict=True):
        fwl_mpl.panel_label(ax, label)
    return fig


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent / "output")
    out.mkdir(parents=True, exist_ok=True)
    for mode in fwl_mpl.MODES:
        fig = specimen(mode)
        problems = fwl_mpl.finish(fig)
        if problems:
            raise SystemExit("layout problems:\n" + "\n".join(problems))
        for ext in ("png", "pdf"):
            fig.savefig(out / f"specimen_{mode}.{ext}", dpi=200)
        plt.close(fig)
        print("wrote", out / f"specimen_{mode}.png")
