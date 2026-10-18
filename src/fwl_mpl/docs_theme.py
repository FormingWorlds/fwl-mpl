"""Forming Worlds Lab theme for Documenter.jl sites.

The stylesheet is the one of :mod:`fwl_visual_language.documenter`: it keeps the
stock ``documenter-light`` and ``documenter-dark`` layouts and changes only their
colours and type, from the same tokens as the figures of :mod:`fwl_mpl`.

Install it into the ``assets`` folder of a Documenter source tree::

    python -m fwl_mpl.docs_theme docs/src/assets

and list ``"assets/fwl.css"`` in ``Documenter.HTML(; assets=[...])``. The
catppuccin themes keep their own colours.
"""

import argparse

from fwl_visual_language.documenter import CSS_NAME, documenter_css, install_documenter_theme

__all__ = ["CSS_NAME", "documenter_css", "install_documenter_theme", "main"]


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
