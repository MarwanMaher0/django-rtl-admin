"""The Unicode isolation helpers."""

import pytest
from django.test import override_settings
from django.utils.safestring import SafeString, mark_safe
from django.utils.translation import override as override_language

from django_rtl_admin import bidi
from django_rtl_admin.bidi import (
    FSI,
    LRI,
    PDI,
    RLI,
    current_direction,
    has_mixed_direction,
    is_isolated,
    is_rtl_language,
    isolate,
    isolate_runs,
    mark_isolated,
    mark_isolated_runs,
    rtl_languages,
    strip_isolates,
    text_direction,
)

ARABIC = "\u0645\u0631\u062d\u0628\u0627"  # مرحبا
HEBREW = "\u05e9\u05dc\u05d5\u05dd"  # שלום


# -- isolate ---------------------------------------------------------------


def test_isolate_defaults_to_first_strong():
    assert isolate("abc") == FSI + "abc" + PDI


@pytest.mark.parametrize(
    ("direction", "opener"), [("auto", FSI), ("ltr", LRI), ("rtl", RLI)]
)
def test_isolate_honours_direction(direction, opener):
    assert isolate("abc", direction) == opener + "abc" + PDI


@pytest.mark.parametrize("value", ["", None])
def test_isolate_passes_through_empty_values(value):
    assert isolate(value) == ""


def test_isolate_rejects_an_unknown_direction():
    with pytest.raises(ValueError, match="direction must be one of"):
        isolate("abc", "sideways")


def test_isolate_coerces_non_strings():
    assert isolate(42) == FSI + "42" + PDI


@override_settings(RTL_ADMIN={"ISOLATION_DIRECTION": "ltr"})
def test_isolate_default_direction_comes_from_settings():
    assert isolate("abc") == LRI + "abc" + PDI


def test_strip_isolates_is_the_inverse_of_isolate():
    original = f"{ARABIC} v1.2.3"
    assert strip_isolates(isolate(original)) == original


def test_strip_isolates_removes_legacy_marks():
    assert strip_isolates("\u200ex\u200fy") == "xy"


def test_is_isolated():
    assert is_isolated(isolate("abc"))
    assert not is_isolated("abc")
    assert not is_isolated("")


# -- direction detection ---------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("hello", "ltr"),
        (ARABIC, "rtl"),
        (HEBREW, "rtl"),
        ("2024-03-05", "ltr"),  # no strong character -> the default
        ("", "ltr"),
        (f"  {ARABIC} hello", "rtl"),
        (f"(hello) {ARABIC}", "ltr"),
    ],
)
def test_text_direction(value, expected):
    assert text_direction(value) == expected


def test_text_direction_default_is_configurable():
    assert text_direction("2024", default="rtl") == "rtl"


def test_has_mixed_direction():
    assert has_mixed_direction(f"{ARABIC} hello")
    assert not has_mixed_direction(ARABIC)
    assert not has_mixed_direction("hello 2024")


@pytest.mark.parametrize(
    ("code", "expected"),
    [("ar", True), ("ar-eg", True), ("AR_EG", True), ("he", True), ("fa", True), ("en", False), ("en-gb", False)],
)
def test_is_rtl_language(code, expected):
    assert is_rtl_language(code) is expected


@override_settings(RTL_ADMIN={"EXTRA_RTL_LANGUAGES": ("tzm",)})
def test_extra_rtl_languages_are_honoured():
    assert is_rtl_language("tzm") is True


@override_settings(LANGUAGES_BIDI=["ps"])
def test_languages_bidi_is_honoured_with_base_code_matching():
    assert "ps" in rtl_languages()
    assert is_rtl_language("ps") is True
    assert is_rtl_language("PS") is True
    assert is_rtl_language("ps-AF") is True
    assert is_rtl_language("ps_af") is True


@override_settings(LANGUAGES_BIDI=["ps-af", "PS"])
def test_languages_bidi_entries_are_matched_raw_and_case_sensitively():
    # Django compares the base subtag against the raw entries, so regional or
    # upper-case spellings do not make "ps" RTL in the document.
    assert is_rtl_language("ps") is False
    assert is_rtl_language("PS") is False
    assert is_rtl_language("ps-AF") is False
    assert is_rtl_language("ps_af") is False


@override_settings(
    LANGUAGES_BIDI=["ar", "ar-dz", "PS", "ps-af", "ps_AF", "he"],
    RTL_ADMIN={"EXTRA_RTL_LANGUAGES": ("Tzm_MA",)},
)
def test_rtl_languages_only_returns_codes_django_can_match():
    languages = rtl_languages()
    assert languages == {"ar", "he", "tzm-ma"}
    for code in languages:
        assert is_rtl_language(code) is True
    assert is_rtl_language("PS") is False
    assert is_rtl_language("ps-af") is False


@override_settings(LANGUAGES_BIDI=[])
def test_lang_info_bidi_flag_does_not_override_languages_bidi():
    assert "ar" not in rtl_languages()
    assert is_rtl_language("ar") is False
    assert is_rtl_language("ar-eg") is False
    with override_language("ar"):
        assert current_direction() == "ltr"


@override_settings(LANGUAGES_BIDI=[], RTL_ADMIN={"EXTRA_RTL_LANGUAGES": ("ar",)})
def test_extra_rtl_languages_stay_additive_without_languages_bidi():
    assert is_rtl_language("ar") is True
    assert is_rtl_language("ar-eg") is True
    with override_language("ar"):
        assert current_direction() == "rtl"


@override_settings(LANGUAGES_BIDI=["ps"])
def test_current_direction_follows_languages_bidi():
    with override_language("ps"):
        assert current_direction() == "rtl"


def test_current_direction_follows_the_active_language():
    with override_language("ar"):
        assert current_direction() == "rtl"
    with override_language("en"):
        assert current_direction() == "ltr"


# -- isolate_runs ----------------------------------------------------------


@pytest.mark.parametrize(
    "run",
    [
        "user@example.com",
        "https://example.com/a?b=1",
        "/srv/archive/2024/report.pdf",
        "v1.2.3",
        "2.0.0-rc.4",
        "2024-03-05",
        "10:45:02",
        "ISBN 978-0-13-468599-1",
        "C:\\Users\\data.csv",
        "AB-1234/X",
    ],
)
def test_isolate_runs_isolates_mixed_runs_inside_rtl_text(run):
    text = f"{ARABIC} {run} {ARABIC}"
    result = isolate_runs(text, base="rtl")
    assert LRI + run + PDI in result
    assert strip_isolates(result) == text


def test_isolate_runs_leaves_a_bare_number_alone_in_rtl():
    text = f"{ARABIC} 1234 {ARABIC}"
    assert isolate_runs(text, base="rtl") == text


def test_isolate_runs_isolates_rtl_runs_inside_ltr_text():
    text = f"Title: {ARABIC} (draft)"
    result = isolate_runs(text, base="ltr")
    assert RLI + ARABIC + PDI in result
    assert strip_isolates(result) == text


def test_isolate_runs_leaves_plain_ltr_text_alone():
    text = "Order 2024-03-05 shipped."
    assert isolate_runs(text, base="ltr") == text


def test_isolate_runs_keeps_glued_punctuation_and_leaves_spaced_punctuation_out():
    # The bracket is glued to the run, so it travels with it; the colon is
    # separated by a space and belongs to the Arabic sentence.
    assert isolate_runs(f"{ARABIC}: (v1.0).", base="rtl") == f"{ARABIC}: {LRI}(v1.0).{PDI}"
    assert isolate_runs(f"{ARABIC}. hello", base="rtl") == f"{ARABIC}. {LRI}hello{PDI}"


def test_isolate_runs_keeps_a_leading_path_separator_inside_the_run():
    text = f"{ARABIC} /srv/archive/report.pdf"
    assert isolate_runs(text, base="rtl") == f"{ARABIC} {LRI}/srv/archive/report.pdf{PDI}"


def test_isolate_runs_rejects_a_bad_base():
    with pytest.raises(ValueError, match="base must be"):
        isolate_runs("x", base="auto")


def test_isolate_runs_uses_the_active_language_by_default():
    with override_language("ar"):
        assert isolate_runs(f"{ARABIC} v1.0") == f"{ARABIC} {LRI}v1.0{PDI}"


@pytest.mark.parametrize("value", ["", None])
def test_isolate_runs_passes_through_empty_values(value):
    assert isolate_runs(value) == value


# -- mark_isolated ---------------------------------------------------------


def test_mark_isolated_returns_safe_text():
    result = mark_isolated("abc")
    assert isinstance(result, SafeString)
    assert result == FSI + "abc" + PDI


def test_mark_isolated_escapes_html():
    result = mark_isolated("<script>alert('x')</script>")
    assert "<script>" not in result
    assert "&lt;script&gt;" in result
    assert result.startswith(FSI) and result.endswith(PDI)


def test_mark_isolated_escapes_attribute_breakers():
    assert mark_isolated('" onmouseover="x') == FSI + "&quot; onmouseover=&quot;x" + PDI


def test_mark_isolated_respects_already_safe_values():
    assert mark_isolated(mark_safe("<b>ok</b>")) == FSI + "<b>ok</b>" + PDI


def test_mark_isolated_without_autoescape_does_not_escape():
    assert mark_isolated("<b>", autoescape=False) == FSI + "<b>" + PDI


def test_mark_isolated_of_none_is_empty_and_safe():
    result = mark_isolated(None)
    assert isinstance(result, SafeString)
    assert result == ""


# -- mark_isolated_runs ----------------------------------------------------


def test_mark_isolated_runs_escapes_html():
    result = mark_isolated_runs(f"{ARABIC} <b>v1.0</b>", base="rtl")
    assert "<b>" not in result
    assert "&lt;" in result


def test_mark_isolated_runs_never_splits_an_html_entity():
    # Isolating the escaped text directly would insert an isolate between "&"
    # and "amp;" and break the entity.
    result = mark_isolated_runs(f"{ARABIC} & {ARABIC}", base="rtl")
    assert "&amp;" in result
    assert "&\u2066amp" not in result


def test_mark_isolated_runs_leaves_safe_markup_untouched():
    markup = mark_safe(f'<a href="/x">{ARABIC} v1.0</a>')
    assert mark_isolated_runs(markup, base="rtl") == markup


def test_mark_isolated_runs_of_none_is_empty_and_safe():
    assert mark_isolated_runs(None) == ""
    assert isinstance(mark_isolated_runs(None), SafeString)


def test_isolate_characters_are_the_documented_code_points():
    assert (bidi.LRI, bidi.RLI, bidi.FSI, bidi.PDI) == (
        "\u2066",
        "\u2067",
        "\u2068",
        "\u2069",
    )
