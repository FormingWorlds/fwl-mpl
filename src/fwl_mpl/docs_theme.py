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

from . import _FONTS, PALETTE, SURFACES

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

# Documenter admonition kind -> palette hue.
_ADMONITIONS = {
    "default": None,
    "info": "azure",
    "success": "emerald",
    "warning": "amber",
    "danger": "vermilion",
    "compat": "teal",
    "todo": "violet",
}

# highlight.js token class -> palette hue.
_SYNTAX = {
    "keyword": "violet",
    "string": "emerald",
    "number": "vermilion",
    "literal": "vermilion",
    "title": "azure",
    "built_in": "teal",
    "type": "teal",
    "attr": "amber",
    "symbol": "olive",
    "meta": "rose",
    "section": "rose",
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
    """WCAG contrast ratio between two ``#RRGGBB`` colours."""
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
    hues = PALETTE[mode]
    safe = {n: _text_safe(c, ink, (bg, sub)) for n, c in hues.items()}
    return {
        "bg": bg,
        "sub": sub,
        "ink": ink,
        "muted": _text_safe(s["muted"], ink, (bg, sub)),
        "line": s["line"],
        "hover": _mix(bg, ink, 0.09),
        "link": safe["azure"],
        "hues": hues,
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
        lines.append(f"  --fwl-{name}-wash: {_mix(t['bg'], color, 0.1)};")
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


def _rule(selectors, *declarations):
    """Format one rule whose selectors all sit under the two-mode scope."""
    sel = ",\n".join(f"{_SCOPE} {s}".rstrip() for s in selectors)
    body = "\n".join(f"  {d};" for d in declarations)
    return f"{sel} {{\n{body}\n}}\n"


def _layout_rules():
    r = []
    r.append(
        _rule(
            ["body", "#documenter .docs-main", "#documenter .docs-main article", ".content"],
            "background-color: var(--fwl-bg)",
            "color: var(--fwl-ink)",
            'font-family: "IBM Plex Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", '
            "Helvetica, Arial, sans-serif",
        )
    )
    r.append(
        _rule(
            [
                ".content h1",
                ".content h2",
                ".content h3",
                ".content h4",
                ".content h5",
                ".content h6",
            ],
            "color: var(--fwl-ink)",
            "font-weight: 500",
            "letter-spacing: -0.005em",
        )
    )
    r.append(_rule([".content strong", ".content b", "th"], "color: inherit", "font-weight: 500"))
    r.append(_rule([".content em", ".content i"], "font-style: italic"))
    r.append(_rule([".content a"], "color: var(--fwl-link)"))
    r.append(
        _rule(
            [
                ".content h1 a.docs-heading-anchor",
                ".content h2 a.docs-heading-anchor",
                ".content h3 a.docs-heading-anchor",
                ".content h4 a.docs-heading-anchor",
                ".content h5 a.docs-heading-anchor",
                ".content h6 a.docs-heading-anchor",
            ],
            "color: inherit",
        )
    )
    r.append(_rule([".content a:hover"], "color: var(--fwl-link)", "text-decoration: underline"))
    r.append(
        _rule(
            [".content hr", "#documenter .docs-main header.docs-navbar", ".docs-footer"],
            "border-color: var(--fwl-line)",
        )
    )
    r.append(
        _rule(["#documenter .docs-main header.docs-navbar"], "background-color: var(--fwl-bg)")
    )
    r.append(
        _rule(
            ["#documenter .docs-main header.docs-navbar a", ".breadcrumb a"],
            "color: var(--fwl-ink)",
        )
    )
    r.append(_rule([".docs-footer", ".docs-footer a"], "color: var(--fwl-muted)"))
    r.append(
        _rule(
            [".content blockquote"],
            "background-color: transparent",
            "border-left: 3px solid var(--fwl-azure-fill)",
            "color: var(--fwl-muted)",
        )
    )
    r.append(
        _rule(
            [".content table", ".content table th", ".content table td"],
            "border-color: var(--fwl-line)",
            "color: var(--fwl-ink)",
        )
    )
    r.append(
        _rule(
            [".content table thead th", ".content table thead td"],
            "background-color: var(--fwl-sub)",
            "color: var(--fwl-ink)",
        )
    )
    r.append(_rule([".content table tbody tr:hover"], "background-color: var(--fwl-sub)"))
    r.append(
        _rule(
            [":focus-visible"],
            "outline: 2px solid var(--fwl-azure-fill)",
            "outline-offset: 2px",
        )
    )
    return r


def _sidebar_rules():
    r = []
    sb = "#documenter .docs-sidebar"
    r.append(
        _rule(
            [sb],
            "background-color: var(--fwl-sub)",
            "border-right: 1px solid var(--fwl-line)",
            "color: var(--fwl-ink)",
        )
    )
    r.append(
        _rule(
            [f"{sb} .docs-package-name", f"{sb} .docs-package-name a"],
            "color: var(--fwl-ink)",
            "font-weight: 500",
            "border-bottom-color: var(--fwl-line)",
        )
    )
    r.append(
        _rule(
            [f"{sb} ul.docs-menu .tocitem", f"{sb} ul.docs-menu .tocitem:hover"],
            "background: transparent",
            "color: var(--fwl-ink)",
        )
    )
    r.append(
        _rule(
            [f"{sb} ul.docs-menu"],
            "border-top-color: var(--fwl-line)",
        )
    )
    r.append(
        _rule(
            [f"{sb} ul.docs-menu a.tocitem:hover", f"{sb} ul.docs-menu label.tocitem:hover"],
            "background-color: var(--fwl-hover)",
            "color: var(--fwl-ink)",
        )
    )
    r.append(
        _rule(
            [
                f"{sb} ul.docs-menu li.is-active",
                f"{sb} ul.docs-menu li.is-active .tocitem",
                f"{sb} ul.docs-menu li.is-active .tocitem:hover",
            ],
            "background: var(--fwl-bg)",
            "color: var(--fwl-ink)",
        )
    )
    r.append(
        _rule(
            [f"{sb} ul.docs-menu li.is-active ul.internal .tocitem:hover"],
            "background: var(--fwl-hover)",
        )
    )
    r.append(
        _rule(
            [f"{sb} ul.docs-menu li.is-active"],
            "border-top-color: var(--fwl-line)",
            "border-bottom-color: var(--fwl-line)",
        )
    )
    r.append(
        _rule(
            [f"{sb} form.docs-search > input", "#documenter-search-query"],
            "background-color: var(--fwl-bg)",
            "border: 1px solid var(--fwl-line)",
            "color: var(--fwl-ink)",
        )
    )
    return r


def _code_rules():
    r = []
    r.append(
        _rule(
            [".content code", ".content kbd", ".content samp"],
            "background-color: var(--fwl-sub)",
            "color: var(--fwl-ink)",
            'font-family: "IBM Plex Mono", JuliaMono, "SFMono-Regular", Menlo, Consolas, monospace',
        )
    )
    r.append(
        _rule(
            [".content pre", ".content pre code"],
            "background-color: var(--fwl-sub)",
            "color: var(--fwl-ink)",
        )
    )
    r.append(
        _rule(
            [".content pre"],
            "border: 1px solid var(--fwl-line)",
            "border-radius: 4px",
        )
    )
    r.append(_rule([".content pre code"], "border: 0"))
    r.append(
        _rule(
            [".hljs", ".content pre code.hljs"],
            "background-color: var(--fwl-sub)",
            "color: var(--fwl-ink)",
        )
    )
    r.append(
        _rule(
            [".hljs-comment", ".hljs-quote", ".hljs-doctag"],
            "color: var(--fwl-muted)",
            "font-style: italic",
        )
    )
    for token, hue in _SYNTAX.items():
        r.append(_rule([f".hljs-{token}"], f"color: var(--fwl-{hue})"))
    r.append(
        _rule(
            [".hljs-name", ".hljs-selector-tag", ".hljs-selector-id", ".hljs-selector-class"],
            "color: var(--fwl-azure)",
        )
    )
    r.append(_rule([".hljs-variable", ".hljs-params", ".hljs-subst"], "color: var(--fwl-ink)"))
    r.append(
        _rule(
            [".hljs-addition"],
            "color: var(--fwl-emerald)",
            "background-color: var(--fwl-emerald-wash)",
        )
    )
    r.append(
        _rule(
            [".hljs-deletion"],
            "color: var(--fwl-vermilion)",
            "background-color: var(--fwl-vermilion-wash)",
        )
    )
    return r


def _block_rules():
    r = []
    for kind, hue in _ADMONITIONS.items():
        border = f"var(--fwl-{hue}-fill)" if hue else "var(--fwl-line)"
        head = f"var(--fwl-{hue})" if hue else "var(--fwl-muted)"
        wash = f"var(--fwl-{hue}-wash)" if hue else "var(--fwl-sub)"
        r.append(
            _rule(
                [f".admonition.is-{kind}"],
                f"border-color: {border}",
                f"background-color: {wash}",
                "border-radius: 4px",
            )
        )
        r.append(
            _rule(
                [f".admonition.is-{kind} > .admonition-header"],
                f"color: {head}",
                "background-color: transparent",
                "font-weight: 500",
            )
        )
        r.append(
            _rule(
                [f".admonition.is-{kind} > .admonition-body"],
                "color: var(--fwl-ink)",
                "background-color: transparent",
            )
        )
    r.append(
        _rule(
            ["details.docstring"],
            "border: 1px solid var(--fwl-line)",
            "border-radius: 4px",
            "background-color: transparent",
        )
    )
    r.append(
        _rule(
            ["details.docstring > summary"],
            "background-color: var(--fwl-sub)",
            "border-bottom-color: var(--fwl-line)",
            "color: var(--fwl-ink)",
        )
    )
    r.append(
        _rule(
            ["details.docstring > section > a.docs-sourcelink", ".docstring-category"],
            "color: var(--fwl-muted)",
        )
    )
    return r


def documenter_css():
    """Return the stylesheet text for Documenter.jl, light and dark.

    Returns
    -------
    str
        CSS that restyles ``documenter-light`` and ``documenter-dark``. It refers
        to the fonts as ``fwl-fonts/<file>`` next to the stylesheet.
    """
    header = (
        "/* Forming Worlds Lab theme for Documenter.jl. Generated by "
        "fwl_mpl.docs_theme from the lab palette. */\n"
    )
    parts = [header, _font_faces()]
    parts += [_variables("light"), _variables("dark")]
    parts += _layout_rules() + _sidebar_rules() + _code_rules() + _block_rules()
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
        Path of the written stylesheet.
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
    parser = argparse.ArgumentParser(prog="python -m fwl_mpl.docs_theme", description=__doc__)
    parser.add_argument("dest", help="assets folder of the Documenter source tree")
    args = parser.parse_args(argv)
    print(install_documenter_theme(args.dest))


if __name__ == "__main__":
    main()
