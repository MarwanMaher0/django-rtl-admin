"""The package ships what it claims to ship."""

import pathlib

import django_rtl_admin

ROOT = pathlib.Path(django_rtl_admin.__file__).parent


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
