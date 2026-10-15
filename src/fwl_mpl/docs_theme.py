"""Forming Worlds Lab theme for Documenter.jl sites.

The stylesheet restyles the stock ``documenter-light`` and ``documenter-dark``
themes with the lab palette and IBM Plex type, so a docs page matches the
figures made with :mod:`fwl_mpl`. It is generated from ``PALETTE`` and
``SURFACES``, which keeps the figures and the pages on one set of colours.

Install it into the ``assets`` folder of a Documenter source tree::

    python -m fwl_mpl.docs_theme docs/src/assets

and list ``"assets/fwl.css"`` in ``Documenter.HTML(; assets=[...])``. The light
theme must stay the primary theme and ``documenter-dark`` the primary dark
theme, which is the Documenter default.
"""

import argparse
import shutil
from pathlib import Path

from . import _FONTS, PALETTE, SURFACES, __version__

__all__ = ["documenter_css", "install_documenter_theme"]

CSS_NAME = "fwl.css"
FONT_DIR = "fwl-fonts"
MIN_CONTRAST = 4.5

# Scope per mode: the primary light theme has no theme class on <html> until a
# reader picks a theme in the settings dialog, which then sets theme--<name>.
_MODE_SELECTOR = {
    "light": 'html:not([class*="theme--"]), html.theme--documenter-light',
    "dark": "html.theme--documenter-dark",
}
_SCOPE = ":is(" + ", ".join(_MODE_SELECTOR.values()) + ")"

# Documenter admonition kind -> palette hue. Other kinds (custom categories,
# details blocks) take the neutral base style.
_ADMONITIONS = {
    "info": "azure",
    "success": "emerald",
    "warning": "amber",
    "danger": "vermilion",
    "compat": "teal",
    "todo": "violet",
}

# highlight.js token class -> palette hue, or "ink" / "muted".
_SYNTAX = {
    "keyword": "violet",
    "string": "emerald",
    "number": "vermilion",
    "literal": "vermilion",
    "title": "azure",
    "name": "azure",
    "tag": "azure",
    "link": "azure",
    "selector-tag": "azure",
    "selector-id": "azure",
    "selector-class": "azure",
    "built_in": "teal",
    "type": "teal",
    "template-variable": "teal",
    "selector-attr": "teal",
    "selector-pseudo": "teal",
    "attr": "amber",
    "attribute": "amber",
    "symbol": "olive",
    "bullet": "olive",
    "meta": "rose",
    "section": "rose",
    "regexp": "rose",
    "variable": "ink",
    "params": "ink",
    "subst": "ink",
    "operator": "ink",
    "punctuation": "ink",
    "code": "ink",
    "comment": "muted",
    "quote": "muted",
    "doctag": "muted",
}

_FONT_FACES = (
    ("IBM Plex Sans", "IBMPlexSans-Regular.ttf", "normal", 400),
    ("IBM Plex Sans", "IBMPlexSans-Italic.ttf", "italic", 400),
    ("IBM Plex Sans", "IBMPlexSans-Medium.ttf", "normal", 500),
    ("IBM Plex Sans", "IBMPlexSans-MediumItalic.ttf", "italic", 500),
    ("IBM Plex Mono", "IBMPlexMono-Regular.ttf", "normal", 400),
)


def _rgb(hex_color):
    h = hex_color.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def _hex(rgb):
    return "#" + "".join(f"{round(max(0, min(255, c))):02X}" for c in rgb)


def _mix(a, b, t):
    """Return the colour a fraction ``t`` of the way from ``a`` to ``b`` (sRGB)."""
    return _hex(tuple(x + (y - x) * t for x, y in zip(_rgb(a), _rgb(b), strict=True)))


def _luminance(hex_color):
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(c) for c in _rgb(hex_color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    """Return the WCAG 2 contrast ratio of two colours.

    Parameters
    ----------
    a, b : str
        Colours as ``#RRGGBB``.

    Returns
    -------
    float
        Ratio between 1 and 21.
    """
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _text_safe(color, ink, backgrounds):
    """Move ``color`` toward ``ink`` until it reads at 4.5:1 on every background."""
    for step in range(101):
        out = _mix(color, ink, step / 100)
        if all(contrast(out, bg) >= MIN_CONTRAST for bg in backgrounds):
            return out
    return ink


def _tokens(mode):
    """Resolve the colour tokens of one mode."""
    s = SURFACES[mode]
    bg, ink = s["background"], s["ink"]
    sub = _mix(bg, ink, 0.045 if mode == "light" else 0.06)
    hover = _mix(bg, ink, 0.09)
    hues = PALETTE[mode]
    washes = {n: _mix(bg, c, 0.1) for n, c in hues.items()}
    # Every text colour must read on every surface it can sit on.
    surfaces = (bg, sub, hover, *washes.values())
    safe = {n: _text_safe(c, ink, surfaces) for n, c in hues.items()}
    return {
        "bg": bg,
        "sub": sub,
        "ink": ink,
        "muted": _text_safe(s["muted"], ink, surfaces),
        "line": s["line"],
        "hover": hover,
        "link": safe["azure"],
        "hues": hues,
        "washes": washes,
        "surfaces": surfaces,
        "safe": safe,
    }


def _variables(mode):
    t = _tokens(mode)
    lines = [
        f"  --fwl-bg: {t['bg']};",
        f"  --fwl-sub: {t['sub']};",
        f"  --fwl-ink: {t['ink']};",
        f"  --fwl-muted: {t['muted']};",
        f"  --fwl-line: {t['line']};",
        f"  --fwl-hover: {t['hover']};",
        f"  --fwl-link: {t['link']};",
    ]
    for name, color in t["safe"].items():
        lines.append(f"  --fwl-{name}: {color};")
    for name, color in t["hues"].items():
        lines.append(f"  --fwl-{name}-fill: {color};")
        lines.append(f"  --fwl-{name}-wash: {t['washes'][name]};")
    # The bundled faces are Sans 400/500 and Mono 400: no faux bold or italic.
    lines += ["  background-color: var(--fwl-bg);", "  font-synthesis: none;"]
    return f"{_MODE_SELECTOR[mode]} {{\n" + "\n".join(lines) + "\n}\n"


def _font_faces():
    out = []
    for family, file, style, weight in _FONT_FACES:
        out.append(
            "@font-face {\n"
            f'  font-family: "{family}";\n'
            f'  src: url("{FONT_DIR}/{file}") format("truetype");\n'
            f"  font-style: {style};\n"
            f"  font-weight: {weight};\n"
            "  font-display: swap;\n"
            "}\n"
        )
    return "\n".join(out)


SANS = (
    '"IBM Plex Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif'
)
MONO = '"IBM Plex Mono", JuliaMono, "SFMono-Regular", Menlo, Consolas, monospace'
_SB = "#documenter .docs-sidebar"
_MENU = f"{_SB} ul.docs-menu"
_HEADINGS = [f".content h{i}" for i in range(1, 7)]

# (selectors, declarations). Each selector is matched at the specificity of the
# stock rule it replaces; the stylesheet loads after the themes, so ties win.
_RULES = [
    # Page, type and text
    (
        ["body", "#documenter .docs-main", "#documenter .docs-main article", ".content"],
        ["background-color: var(--fwl-bg)", "color: var(--fwl-ink)", f"font-family: {SANS}"],
    ),
    (["button", "input", "optgroup", "select", "textarea"], [f"font-family: {SANS}"]),
    (_HEADINGS, ["color: var(--fwl-ink)", "font-weight: 500", "letter-spacing: -0.005em"]),
    ([f"{h} a.docs-heading-anchor" for h in _HEADINGS], ["color: inherit"]),
    ([f"{h} a.docs-heading-anchor code" for h in _HEADINGS], ["color: var(--fwl-ink)"]),
    ([".content strong", ".content b", "th"], ["color: inherit", "font-weight: 500"]),
    ([".content a", ".content a code", ".content a:hover code"], ["color: var(--fwl-link)"]),
    ([".content a:hover"], ["color: var(--fwl-link)", "text-decoration: underline"]),
    ([".content hr", ".modal-card-body hr"], ["background-color: var(--fwl-line)", "border: 0"]),
    (
        [".content blockquote"],
        [
            "background-color: transparent",
            "border-left: 3px solid var(--fwl-azure-fill)",
            "color: var(--fwl-muted)",
        ],
    ),
    (
        [".content table", ".content table th", ".content table td"],
        ["border-color: var(--fwl-line)", "color: var(--fwl-ink)"],
    ),
    (
        [".content table thead th", ".content table thead td"],
        ["background-color: var(--fwl-sub)", "color: var(--fwl-ink)"],
    ),
    ([".content table tbody tr:hover"], ["background-color: var(--fwl-sub)"]),
    ([":focus-visible"], ["outline: 2px solid var(--fwl-azure-fill)", "outline-offset: 2px"]),
    # Navbar, breadcrumb, footer, footnotes, banners
    (
        ["#documenter .docs-main header.docs-navbar"],
        ["background-color: var(--fwl-bg)", "border-color: var(--fwl-line)"],
    ),
    (["#documenter .docs-main header.docs-navbar a", ".breadcrumb a"], ["color: var(--fwl-ink)"]),
    ([".breadcrumb li + li::before"], ["color: var(--fwl-muted)"]),
    (
        ["#documenter .docs-main .docs-footer"],
        ["border-top-color: var(--fwl-line)", "color: var(--fwl-muted)"],
    ),
    (["#documenter .docs-main .docs-footer a"], ["color: var(--fwl-link)"]),
    (["#documenter .docs-main section.footnotes"], ["border-top-color: var(--fwl-line)"]),
    (
        [".content section.footnotes a.tag.is-link:not(body)"],
        ["background-color: var(--fwl-sub)", "color: var(--fwl-link)"],
    ),
    (
        [".outdated-warning-overlay", ".dev-warning-overlay"],
        [
            "background-color: var(--fwl-sub)",
            "border-color: var(--fwl-line)",
            "color: var(--fwl-ink)",
            "box-shadow: none",
        ],
    ),
    ([".outdated-warning-overlay a", ".dev-warning-overlay a"], ["color: var(--fwl-link)"]),
    # Sidebar
    (
        [_SB],
        [
            "background-color: var(--fwl-sub)",
            "border-right: 1px solid var(--fwl-line)",
            "color: var(--fwl-ink)",
        ],
    ),
    (
        [
            f"{_SB} .docs-package-name",
            f"{_SB} .docs-package-name a",
            f"{_SB} .docs-package-name a:hover",
        ],
        ["color: var(--fwl-ink)", "font-weight: 500", "border-bottom-color: var(--fwl-line)"],
    ),
    (
        [f"{_MENU} .tocitem", f"{_MENU} .tocitem:hover"],
        ["background: transparent", "color: var(--fwl-ink)"],
    ),
    ([_MENU, f"{_MENU} ul.internal"], ["border-top-color: var(--fwl-line)"]),
    ([f"{_MENU} > li li"], ["border-left-color: var(--fwl-line)"]),
    (
        [f"{_MENU} a.tocitem:hover", f"{_MENU} label.tocitem:hover"],
        ["background-color: var(--fwl-hover)", "color: var(--fwl-ink)"],
    ),
    (
        [
            f"{_MENU} li.is-active",
            f"{_MENU} li.is-active .tocitem",
            f"{_MENU} li.is-active .tocitem:hover",
        ],
        ["background: var(--fwl-bg)", "color: var(--fwl-ink)"],
    ),
    ([f"{_MENU} li.is-active ul.internal .tocitem:hover"], ["background: var(--fwl-hover)"]),
    (
        [f"{_MENU} li.is-active"],
        ["border-top-color: var(--fwl-line)", "border-bottom-color: var(--fwl-line)"],
    ),
    ([f"{_MENU}::-webkit-scrollbar-thumb"], ["background: var(--fwl-line)"]),
    ([f"{_MENU}::-webkit-scrollbar-thumb:hover"], ["background: var(--fwl-muted)"]),
    (
        [f"{_SB} #documenter-search-query"],
        [
            "background-color: var(--fwl-bg)",
            "border: 1px solid var(--fwl-line)",
            "color: var(--fwl-muted)",
        ],
    ),
    ([f"{_SB} .docs-version-selector"], ["border-top-color: var(--fwl-line)"]),
    (
        [f"{_SB} .docs-version-selector .button.is-static", f"{_SB} .docs-version-selector select"],
        [
            "background-color: var(--fwl-bg)",
            "border-color: var(--fwl-line)",
            "color: var(--fwl-muted)",
        ],
    ),
    # Settings and search dialogs
    (
        [".modal-card-head", ".modal-card-body", ".modal-card-foot"],
        [
            "background-color: var(--fwl-bg)",
            "border-color: var(--fwl-line)",
            "color: var(--fwl-ink)",
        ],
    ),
    ([".modal-card-title", ".modal-card-body .label"], ["color: var(--fwl-ink)"]),
    ([".modal-card-body a"], ["color: var(--fwl-link)"]),
    (
        [".select select", ".input", ".textarea"],
        [
            "background-color: var(--fwl-bg)",
            "border-color: var(--fwl-line)",
            "color: var(--fwl-ink)",
        ],
    ),
    (
        [".control.has-icons-right .icon", ".control.has-icons-left .icon"],
        ["color: var(--fwl-muted)"],
    ),
    (
        # Bulma sets this utility colour with !important, so only !important beats it.
        [".has-text-primary-dark"],
        ["color: var(--fwl-link) !important"],
    ),
    (
        [".input:focus", ".textarea:focus", ".select select:focus"],
        [
            "border-color: var(--fwl-azure-fill)",
            "box-shadow: 0 0 0 0.125em var(--fwl-azure-wash)",
        ],
    ),
    (
        ["kbd.search-modal-key-hints"],
        ["border-color: var(--fwl-line)", "box-shadow: 0 2px 0 1px var(--fwl-line)"],
    ),
    ([".search-result-link"], ["color: var(--fwl-ink)"]),
    (
        [".search-result-link:hover", ".search-result-link:focus"],
        ["background-color: var(--fwl-hover)"],
    ),
    ([".search-result-title"], ["color: var(--fwl-ink)"]),
    (
        [".property-search-result-badge", ".search-filter"],
        ["background-color: var(--fwl-sub)", "color: var(--fwl-ink)"],
    ),
    ([".search-filter-selected"], ["background-color: var(--fwl-azure-wash)"]),
    ([".search-result-highlight"], ["background-color: var(--fwl-amber-wash)"]),
    # Code
    (
        [".content code", ".content kbd:not(body)", ".content samp"],
        ["background-color: var(--fwl-sub)", "color: var(--fwl-ink)", f"font-family: {MONO}"],
    ),
    (
        [".content pre", ".content pre code", ".hljs", ".content pre code.hljs"],
        ["background-color: var(--fwl-sub)", "color: var(--fwl-ink)"],
    ),
    ([".content pre"], ["border: 1px solid var(--fwl-line)", "border-radius: 4px"]),
    (["pre .copy-button"], ["color: var(--fwl-muted)"]),
    (
        ["pre .copy-button:hover", "pre .copy-button:focus"],
        ["color: var(--fwl-link)", "background: var(--fwl-hover)"],
    ),
    (["pre .copy-button.success"], ["color: var(--fwl-emerald)"]),
    (["pre .copy-button.error"], ["color: var(--fwl-vermilion)"]),
    ([".content pre code"], ["border: 0"]),
    *[([f".hljs-{token}"], [f"color: var(--fwl-{hue})"]) for token, hue in _SYNTAX.items()],
    ([".hljs-emphasis"], ["font-style: italic"]),
    ([".hljs-strong"], ["font-weight: 500"]),
    (["code.language-julia-repl > span.hljs-meta"], ["color: var(--fwl-emerald)"]),
    (
        [".hljs-addition"],
        ["color: var(--fwl-emerald)", "background-color: var(--fwl-emerald-wash)"],
    ),
    (
        [".hljs-deletion"],
        ["color: var(--fwl-vermilion)", "background-color: var(--fwl-vermilion-wash)"],
    ),
    # Admonitions: the base style serves custom categories and details blocks
    (
        [".admonition"],
        ["border-color: var(--fwl-line)", "background-color: var(--fwl-sub)", "border-radius: 4px"],
    ),
    (
        [".admonition > .admonition-header"],
        ["color: var(--fwl-muted)", "background-color: transparent", "font-weight: 500"],
    ),
    (
        [".admonition > .admonition-body"],
        ["color: var(--fwl-ink)", "background-color: transparent"],
    ),
    *[
        rule
        for kind, hue in _ADMONITIONS.items()
        for rule in (
            (
                [f".admonition.is-{kind}"],
                [
                    f"border-color: var(--fwl-{hue}-fill)",
                    f"background-color: var(--fwl-{hue}-wash)",
                ],
            ),
            ([f".admonition.is-{kind} > .admonition-header"], [f"color: var(--fwl-{hue})"]),
            ([f".admonition.is-{kind} > .admonition-body"], ["color: var(--fwl-ink)"]),
        )
    ],
    # Docstrings
    (
        ["details.docstring"],
        [
            "border: 1px solid var(--fwl-line)",
            "border-radius: 4px",
            "background-color: transparent",
        ],
    ),
    (
        ["details.docstring > summary"],
        [
            "background-color: var(--fwl-sub)",
            "border-bottom-color: var(--fwl-line)",
            "color: var(--fwl-ink)",
        ],
    ),
    (["details.docstring > summary::before", ".docstring-category"], ["color: var(--fwl-muted)"]),
    (
        [
            "details.docstring > section > a.docs-sourcelink:not(body)",
            "details.docstring > section > a.docs-sourcelink:not(body):hover",
        ],
        [
            "background-color: var(--fwl-hover)",
            "border-color: transparent",
            "color: var(--fwl-ink)",
        ],
    ),
]


def _rule(selectors, declarations):
    """Format one rule whose selectors all sit under the two-mode scope."""
    sel = ",\n".join(f"{_SCOPE} {s}" for s in selectors)
    body = "\n".join(f"  {d};" for d in declarations)
    return f"{sel} {{\n{body}\n}}\n"


def documenter_css():
    """Return the stylesheet text for Documenter.jl, light and dark.

    Returns
    -------
    str
        CSS that restyles ``documenter-light`` and ``documenter-dark``. It refers
        to the fonts as ``fwl-fonts/<file>`` next to the stylesheet.
    """
    header = (
        f"/* Forming Worlds Lab theme for Documenter.jl (fwl-mpl {__version__}, "
        "Documenter.jl 1.19 class names). Generated by fwl_mpl.docs_theme from the "
        "lab palette; edit the generator, not this file. */\n"
    )
    parts = [header, _font_faces(), _variables("light"), _variables("dark")]
    parts += [_rule(sel, decl) for sel, decl in _RULES]
    return "\n".join(parts)


def install_documenter_theme(dest):
    """Write the stylesheet and the IBM Plex fonts into ``dest``.

    Parameters
    ----------
    dest : str or pathlib.Path
        Target folder, normally ``docs/src/assets`` of a Documenter source tree.
        It is created if it does not exist.

    Returns
    -------
    pathlib.Path
        Path of the written stylesheet. Existing files of the same names are
        replaced.

    Raises
    ------
    OSError
        If ``dest`` exists and is not a folder, or cannot be written.
    """
    dest = Path(dest)
    fonts = dest / FONT_DIR
    fonts.mkdir(parents=True, exist_ok=True)
    for _, file, _, _ in _FONT_FACES:
        shutil.copyfile(_FONTS / file, fonts / file)
    shutil.copyfile(_FONTS / "OFL.txt", fonts / "OFL.txt")
    css = dest / CSS_NAME
    css.write_text(documenter_css(), encoding="utf-8")
    return css


def main(argv=None):
    """Command line entry point: ``python -m fwl_mpl.docs_theme DEST``."""
    parser = argparse.ArgumentParser(
        prog="python -m fwl_mpl.docs_theme",
        description="Write the Forming Worlds Lab Documenter.jl stylesheet and fonts.",
    )
    parser.add_argument("dest", help="assets folder of the Documenter source tree")
    args = parser.parse_args(argv)
    print(install_documenter_theme(args.dest))


if __name__ == "__main__":
    main()
