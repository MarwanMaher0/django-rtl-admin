"""The package ships what it claims to ship."""

import pathlib
import re

import pytest

import django_rtl_admin

ROOT = pathlib.Path(django_rtl_admin.__file__).parent
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_the_stylesheet_is_part_of_the_package():
    assert (ROOT / "static" / "django_rtl_admin" / "css" / "rtl-admin.css").is_file()


def test_the_switcher_script_is_part_of_the_package():
    assert (ROOT / "static" / "django_rtl_admin" / "js" / "language_switcher.js").is_file()


def test_the_templates_are_part_of_the_package():
    assert (ROOT / "templates" / "admin" / "base_site.html").is_file()
    assert (ROOT / "templates" / "django_rtl_admin" / "base_site.html").is_file()
    assert (ROOT / "templates" / "django_rtl_admin" / "language_switcher.html").is_file()


def test_compiled_translations_are_part_of_the_package():
    for code in ("ar", "ckb", "fa", "he", "ug", "ur"):
        assert (ROOT / "locale" / code / "LC_MESSAGES" / "django.mo").is_file()


def test_the_type_marker_is_part_of_the_package():
    # PEP 561: without it type checkers ignore the package's annotations.
    assert (ROOT / "py.typed").is_file()


def test_the_public_api_is_importable():
    for name in django_rtl_admin.__all__:
        assert getattr(django_rtl_admin, name) is not None


def test_the_stylesheet_prefers_logical_properties():
    css = (ROOT / "static" / "django_rtl_admin" / "css" / "rtl-admin.css").read_text()
    logical = css.count("-inline-start") + css.count("-inline-end") + css.count("inset-inline")
    assert logical > 60


def test_the_sdist_includes_governance_and_nox_files():
    for name in ("noxfile.py", "CONTRIBUTING.md", "SECURITY.md"):
        assert (REPO_ROOT / name).is_file()
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for entry in ('"/noxfile.py"', '"/CONTRIBUTING.md"', '"/SECURITY.md"'):
        assert entry in pyproject
    assert re.search(r"(?m)^fail_under\s*=\s*95\s*$", pyproject)


def test_github_workflows_pin_actions_by_full_sha():
    workflows_dir = REPO_ROOT / ".github" / "workflows"
    if not workflows_dir.is_dir():
        pytest.skip("workflow files are only present in a repository checkout")
    pinned = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}\s+#\s*v\d+")
    for workflow in sorted(workflows_dir.glob("*.yml")):
        text = workflow.read_text(encoding="utf-8")
        uses = re.findall(r"^\s*(?:-\s*)?uses:\s*(.+?)\s*$", text, flags=re.MULTILINE)
        assert uses, f"no uses: steps found in {workflow.name}"
        for ref in uses:
            assert pinned.match(ref), f"unpinned action in {workflow.name}: {ref}"
    ci_text = (workflows_dir / "ci.yml").read_text(encoding="utf-8")
    assert "\n  sdist:\n" in ci_text
    assert 'pytest -m "not e2e"' in ci_text


def test_dependabot_tracks_github_actions_and_pip_weekly_in_groups():
    dependabot = REPO_ROOT / ".github" / "dependabot.yml"
    if not dependabot.parent.is_dir():
        pytest.skip("dependabot.yml is only present in a repository checkout")
    text = dependabot.read_text(encoding="utf-8")
    assert 'package-ecosystem: "github-actions"' in text
    assert 'package-ecosystem: "pip"' in text
    assert 'interval: "weekly"' in text
    assert "groups:" in text
