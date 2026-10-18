"""Documenter.jl theme: the wrapper of fwl_visual_language.documenter and its command line."""

import re
import runpy
import sys

import pytest
from fwl_visual_language import documenter

from fwl_mpl import docs_theme


def test_stylesheet_is_the_token_stylesheet():
    assert docs_theme.documenter_css() == documenter.documenter_css()
    assert docs_theme.CSS_NAME == "fwl.css"


def test_install_writes_stylesheet_fonts_and_licences(tmp_path):
    out = docs_theme.install_documenter_theme(tmp_path / "assets")
    assert out == tmp_path / "assets" / "fwl.css"
    assert out.read_text(encoding="utf-8") == documenter.documenter_css()
    fonts = tmp_path / "assets" / "fwl-fonts"
    assert sorted(p.name for p in fonts.glob("*.woff2"))
    assert (fonts / "OFL-Geist.txt").is_file()
    assert (fonts / "OFL-Inter.txt").is_file()


def test_every_font_the_stylesheet_names_is_installed_next_to_it(tmp_path):
    out = docs_theme.install_documenter_theme(tmp_path)
    files = re.findall(r'url\("?(fwl-fonts/[^")]+)"?\)', out.read_text(encoding="utf-8"))
    assert len(files) >= 4
    assert [f for f in files if not (tmp_path / f).is_file()] == []


def test_install_is_idempotent(tmp_path):
    first = docs_theme.install_documenter_theme(tmp_path).read_bytes()
    second = docs_theme.install_documenter_theme(tmp_path).read_bytes()
    assert first == second


def test_command_line_installs_and_prints_the_path(tmp_path, capsys):
    docs_theme.main([str(tmp_path / "a")])
    assert capsys.readouterr().out.strip() == str(tmp_path / "a" / "fwl.css")
    assert (tmp_path / "a" / "fwl.css").is_file()


def test_module_runs_as_a_script(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["fwl_mpl.docs_theme", str(tmp_path)])
    monkeypatch.delitem(sys.modules, "fwl_mpl.docs_theme")
    runpy.run_module("fwl_mpl.docs_theme", run_name="__main__")
    assert (tmp_path / "fwl.css").is_file()


def test_install_into_a_file_path_raises(tmp_path):
    target = tmp_path / "assets"
    target.write_text("not a folder")
    with pytest.raises(OSError):
        docs_theme.install_documenter_theme(target)
