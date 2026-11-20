"""Locale-aware number, date and currency formatting."""

import datetime
import decimal
import sys
from types import ModuleType

import django
import pytest
from django.conf import global_settings
from django.test import override_settings
from django.utils import formats, timezone, translation

from django_rtl_admin import formatting
from django_rtl_admin.formatting import (
    DIGITS,
    format_currency,
    format_date,
    format_datetime,
    format_filesize,
    format_number,
    format_percent,
    format_time,
    format_timedelta,
    numbering_system,
    transliterate_digits,
)

ARABIC_INDIC = DIGITS["arab"]
EXTENDED = DIGITS["arabext"]


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        ("en", "latn"),
        ("en-gb", "latn"),
        ("ar", "latn"),  # CLDR: plain "ar" uses Latin digits
        ("ar-eg", "arab"),
        ("fa", "arabext"),
        ("he", "latn"),
    ],
)
def test_numbering_system_follows_the_locale(language, expected):
    assert numbering_system(language) == expected


@override_settings(RTL_ADMIN={"NUMERALS": "arab"})
def test_numbering_system_can_be_forced():
    assert numbering_system("en") == "arab"


def test_numbering_system_falls_back_without_babel(monkeypatch):
    monkeypatch.setattr(formatting, "HAS_BABEL", False)
    assert numbering_system("ar-eg") == "arab"
    assert numbering_system("ar-dj") == "arab"
    assert numbering_system("ar-ae") == "latn"  # CLDR: the Gulf uses Latin digits
    assert numbering_system("fa") == "arabext"
    assert numbering_system("ps") == "arabext"
    assert numbering_system("ur-in") == "arabext"
    assert numbering_system("dv") == "latn"  # CLDR: Maldives uses Latin digits
    assert numbering_system("en") == "latn"


def test_transliterate_digits_round_trips():
    assert transliterate_digits("2024-03-05", "arab") == "٢٠٢٤-٠٣-٠٥"
    assert transliterate_digits("٢٠٢٤", "latn") == "2024"
    assert transliterate_digits("1", "arabext") == "۱"


def test_transliterate_digits_leaves_other_characters_alone():
    assert transliterate_digits("v1.2-rc", "arab") == "v١.٢-rc"


def test_transliterate_digits_rejects_an_unknown_system():
    with pytest.raises(ValueError, match="Unknown numbering system"):
        transliterate_digits("1", "roman")


def test_format_number_uses_arabic_indic_digits_for_ar_eg():
    result = format_number(1234567.891, language="ar-eg")
    assert all(char not in result for char in "0123456789")
    assert any(char in result for char in ARABIC_INDIC)


def test_format_number_uses_latin_digits_for_english():
    assert format_number(1234567, language="en") == "1,234,567"


def test_format_number_honours_decimal_positions():
    assert format_number(decimal.Decimal("2.5"), language="en", decimal_pos=2) == "2.50"


def test_format_number_can_drop_grouping():
    assert format_number(1234567, language="en", grouping=False) == "1234567"


@pytest.mark.parametrize("value", [None, ""])
def test_format_number_of_an_empty_value_is_empty(value):
    assert format_number(value) == ""


def test_format_number_uses_fallback_tables_without_babel(monkeypatch):
    monkeypatch.setattr(formatting, "HAS_BABEL", False)
    result = format_number(1234, language="ar-eg")
    assert any(char in result for char in ARABIC_INDIC)


# ١٬٢٣٤٬٥٦٧٫٨٩١ -- escapes keep the CLDR separators unambiguous.
AR_EG_1234567_891 = "\u0661\u066c\u0662\u0663\u0664\u066c\u0665\u0666\u0667\u066b\u0668\u0669\u0661"
# ۱٬۲۳۴٬۵۶۷٫۸۹۱
FA_1234567_891 = "\u06f1\u066c\u06f2\u06f3\u06f4\u066c\u06f5\u06f6\u06f7\u066b\u06f8\u06f9\u06f1"


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        ("en", "1,234,567.891"),
        ("he", "1,234,567.891"),
        ("ar", "1,234,567.891"),
        ("ar-ma", "1.234.567,891"),
        ("ar-dz", "1.234.567,891"),
        ("dv", "12,34,567.891"),
        ("en-in", "12,34,567.891"),
        ("kk", "1\xa0234\xa0567,891"),
        ("ar-eg", AR_EG_1234567_891),
        ("fa", FA_1234567_891),
        ("ur-in", FA_1234567_891),
    ],
)
def test_format_number_uses_cldr_separators_without_babel(monkeypatch, language, expected):
    monkeypatch.setattr(formatting, "HAS_BABEL", False)
    assert format_number(1234567.891, language=language) == expected


def test_format_number_without_babel_honours_decimal_pos_and_grouping(monkeypatch):
    monkeypatch.setattr(formatting, "HAS_BABEL", False)
    # Explicit positions always group by three, even in Indian-style locales.
    assert format_number(1234567.891, language="dv", decimal_pos=2) == "1,234,567.89"
    assert format_number(1234567, language="en", grouping=False) == "1234567"
    assert format_number(1234567.891, language="dv", grouping=False) == "1234567.891"
    assert (
        format_number(1234567.891, language="ar-eg", grouping=False)
        == "\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u066b\u0668\u0669\u0661"
    )


def test_format_number_without_babel_rounds_like_babel(monkeypatch):
    monkeypatch.setattr(formatting, "HAS_BABEL", False)
    # The default pattern keeps at most three fraction digits, half-to-even,
    # and strips trailing zeros; the sign survives rounding to zero.
    assert format_number(decimal.Decimal("1.2345"), language="en") == "1.234"
    assert format_number(decimal.Decimal("1.2355"), language="en") == "1.236"
    assert format_number(decimal.Decimal("1234.500"), language="en") == "1,234.5"
    assert format_number(decimal.Decimal("-0.0001"), language="en") == "-0"
    # An explicit position rounds half-to-even to exactly that many digits.
    assert format_number(2.675, language="en", decimal_pos=2) == "2.68"
    assert format_number(decimal.Decimal("-0.001"), language="en", decimal_pos=2) == "-0.00"
    assert format_number(decimal.Decimal("2.5"), language="en", decimal_pos=2) == "2.50"
    # Huge inputs expand fully instead of switching to scientific notation.
    assert format_number(10**20, language="en") == "100,000,000,000,000,000,000"
    assert format_number(10**20, language="en", decimal_pos=2) == "100,000,000,000,000,000,000.00"


BIG_30_DIGITS = decimal.Decimal("123456789012345678901234567890")
BIG_30_DIGITS_EN = "123,456,789,012,345,678,901,234,567,890"
BIG_30_SIG_FIGS = decimal.Decimal("1234567890123456789012345678.915")
BIG_30_SIG_FIGS_EN = "1,234,567,890,123,456,789,012,345,678.915"


@pytest.mark.skipif(not formatting.HAS_BABEL, reason="Babel is not installed")
def test_format_number_keeps_every_digit_of_huge_decimals_with_babel():
    # Babel raises InvalidOperation beyond its context precision, so its
    # fallback renderer handles the value; every digit must survive.
    assert format_number(BIG_30_DIGITS, language="en") == BIG_30_DIGITS_EN
    assert format_number(BIG_30_DIGITS, language="en", decimal_pos=2) == BIG_30_DIGITS_EN + ".00"


def test_format_number_without_babel_keeps_every_digit_of_huge_decimals(monkeypatch):
    monkeypatch.setattr(formatting, "HAS_BABEL", False)
    # normalize() runs under the widened context, so values beyond the
    # default 28-digit precision are not rounded; rounding still applies
    # to the fraction at an explicit position, half-to-even.
    assert format_number(BIG_30_DIGITS, language="en") == BIG_30_DIGITS_EN
    assert format_number(BIG_30_DIGITS, language="en", decimal_pos=2) == BIG_30_DIGITS_EN + ".00"
    assert format_number(BIG_30_SIG_FIGS, language="en") == BIG_30_SIG_FIGS_EN
    assert (
        format_number(BIG_30_SIG_FIGS, language="en", decimal_pos=2)
        == "1,234,567,890,123,456,789,012,345,678.92"
    )


def test_format_number_without_babel_leaves_non_numeric_values_to_django(monkeypatch):
    monkeypatch.setattr(formatting, "HAS_BABEL", False)
    assert format_number("abc", language="en") == "abc"


def test_format_currency_without_babel_uses_cldr_separators(monkeypatch):
    monkeypatch.setattr(formatting, "HAS_BABEL", False)
    # ٣٤٩٫٩٠ USD
    result = format_currency(decimal.Decimal("349.90"), "USD", language="ar-eg")
    assert result == "\u0663\u0664\u0669\u066b\u0669\u0660\xa0USD"


PARITY_LANGUAGES = [
    "ar",
    "ar-eg",
    "ar-ma",
    "ar-dz",
    "ar-ae",
    "fa",
    "he",
    "ur",
    "ur-in",
    "en",
    "en-in",
    "dv",
    "ckb",
    "ps",
    "kk",
]

PARITY_CASES = [
    (1234567.891, None),
    (1234567.891, 2),
    (1234567, 2),
    (decimal.Decimal("1234.500"), None),
    (decimal.Decimal("1.2345"), None),
    (2.675, 2),
    (-1234567.891, None),
    (decimal.Decimal("-0.001"), 2),
    (decimal.Decimal("-0.0001"), None),
    (0.25, 0),
    (10**20, None),
    (decimal.Decimal("0.5"), None),
    (0, 2),
]


@pytest.mark.skipif(not formatting.HAS_BABEL, reason="Babel is not installed")
@pytest.mark.parametrize("language", PARITY_LANGUAGES)
@pytest.mark.parametrize(("value", "decimal_pos"), PARITY_CASES)
def test_format_number_matches_babel_without_it_installed(
    monkeypatch, language, value, decimal_pos
):
    with_babel = format_number(value, language=language, decimal_pos=decimal_pos)
    monkeypatch.setattr(formatting, "HAS_BABEL", False)
    without_babel = format_number(value, language=language, decimal_pos=decimal_pos)
    assert without_babel == with_babel


@pytest.mark.skipif(not formatting.HAS_BABEL, reason="Babel is not installed")
@pytest.mark.parametrize("language", ["en", "ar-eg", "dv", "en-in", "kk"])
def test_ungrouped_format_number_matches_babel_without_it_installed(monkeypatch, language):
    with_babel = format_number(1234567.891, language=language, grouping=False)
    monkeypatch.setattr(formatting, "HAS_BABEL", False)
    without_babel = format_number(1234567.891, language=language, grouping=False)
    assert without_babel == with_babel


@override_settings(RTL_ADMIN={"USE_BABEL": False})
def test_use_babel_setting_disables_babel():
    result = format_number(1234, language="ar-eg")
    assert any(char in result for char in ARABIC_INDIC)


def test_format_currency_uses_the_locale_numerals():
    result = format_currency(decimal.Decimal("349.90"), "EGP", language="ar-eg")
    assert any(char in result for char in ARABIC_INDIC)


@override_settings(RTL_ADMIN={"CURRENCY": "EUR"})
def test_format_currency_defaults_to_the_configured_currency():
    assert "€" in format_currency(10, language="en") or "EUR" in format_currency(10, language="en")


def test_format_currency_falls_back_without_babel(monkeypatch):
    monkeypatch.setattr(formatting, "HAS_BABEL", False)
    assert "USD" in format_currency(10, "USD", language="en")


@pytest.mark.parametrize("use_babel", [True, False])
@pytest.mark.parametrize("language", ["en", "ar-eg"])
def test_format_currency_accepts_numeric_strings(monkeypatch, use_babel, language):
    if not use_babel:
        monkeypatch.setattr(formatting, "HAS_BABEL", False)
    output = format_currency("349.90", "USD", language=language)
    assert output
    assert output != "349.90"


@pytest.mark.parametrize("use_babel", [True, False])
@pytest.mark.parametrize("language", ["en", "ar-eg"])
@pytest.mark.parametrize(
    "value",
    [
        "abc",
        [],
        {},
        float("nan"),
        float("inf"),
        float("-inf"),
        decimal.Decimal("NaN"),
        decimal.Decimal("Infinity"),
        "NaN",
        "Infinity",
        "-Infinity",
    ],
)
def test_format_currency_rejects_non_numeric_input(monkeypatch, use_babel, language, value):
    if not use_babel:
        monkeypatch.setattr(formatting, "HAS_BABEL", False)
    with pytest.raises(ValueError, match="Currency value must be numeric"):
        format_currency(value, language=language)


def test_format_percent():
    assert format_percent(0.256, language="en").startswith("26")


@pytest.mark.parametrize("use_babel", [True, False])
@pytest.mark.parametrize(
    ("language", "value", "expected"),
    [
        ("en", 0.125, "12%"),
        ("en", 0.135, "14%"),
        ("en", -0.5, "-50%"),
        ("ar-eg", 0.125, "١٢%"),
        ("ar-eg", 0.135, "١٤%"),
        ("ar-eg", -0.5, "-٥٠%"),
        ("fa", 0.125, "۱۲%"),
        ("fa", 0.135, "۱۴%"),
        ("fa", -0.5, "-۵۰%"),
    ],
)
def test_format_percent_rounds_half_even(use_babel, language, value, expected):
    with override_settings(RTL_ADMIN={"USE_BABEL": use_babel}):
        assert format_percent(value, language=language) == expected


@pytest.mark.parametrize("use_babel", [True, False])
@pytest.mark.parametrize("language", ["en", "ar-eg", "fa"])
@pytest.mark.parametrize("value", ["abc", float("nan"), float("inf")])
def test_format_percent_rejects_invalid_values(use_babel, language, value):
    with (
        override_settings(RTL_ADMIN={"USE_BABEL": use_babel}),
        pytest.raises(ValueError, match="Percentage value must be numeric and finite"),
    ):
        format_percent(value, language=language)


@pytest.mark.parametrize("use_babel", [True, False])
@pytest.mark.parametrize("language", ["en", "ar-eg", "fa"])
@pytest.mark.parametrize("code, canonical", [("usd", "USD"), (" eur ", "EUR")])
def test_format_currency_normalizes_codes(use_babel, language, code, canonical):
    with override_settings(RTL_ADMIN={"USE_BABEL": use_babel}):
        assert format_currency(1, code, language=language) == format_currency(
            1, canonical, language=language
        )


@pytest.mark.parametrize("use_babel", [True, False])
@pytest.mark.parametrize("language", ["en", "ar-eg", "fa"])
@pytest.mark.parametrize("code", ["US", "UŚD", "   "])
def test_format_currency_rejects_invalid_codes(use_babel, language, code):
    with (
        override_settings(RTL_ADMIN={"USE_BABEL": use_babel}),
        pytest.raises(ValueError, match="Currency code must be three ASCII letters"),
    ):
        format_currency(1, code, language=language)


@pytest.mark.parametrize("use_babel", [True, False])
@pytest.mark.parametrize("language", ["en", "ar-eg", "fa"])
@pytest.mark.parametrize("code", ["", None])
def test_format_currency_falls_back_to_the_configured_currency(use_babel, language, code):
    with override_settings(RTL_ADMIN={"USE_BABEL": use_babel, "CURRENCY": "EUR"}):
        assert format_currency(1, code, language=language) == format_currency(
            1, "EUR", language=language
        )


@pytest.mark.parametrize("use_babel", [True, False])
@pytest.mark.parametrize("language", ["en", "ar-eg", "fa"])
def test_format_currency_rejects_a_non_string_code(use_babel, language):
    with (
        override_settings(RTL_ADMIN={"USE_BABEL": use_babel}),
        pytest.raises(ValueError, match="Currency code must be three ASCII letters, got 5"),
    ):
        format_currency(1, 5, language=language)  # type: ignore[arg-type]


SAMPLE_DATETIME = datetime.datetime(2024, 3, 5, 14, 30, 9)


@override_settings(RTL_ADMIN={"USE_BABEL": False})
@pytest.mark.parametrize("fmt", ["short", "medium", "long", "full"])
@pytest.mark.parametrize(
    ("language", "date", "short_date", "time", "joiner", "short_joiner"),
    [
        ("ar", "5 مارس، 2024", "05\u200f/03\u200f/2024", "2:30 م", " ", " "),
        ("ar-eg", "٥ مارس، ٢٠٢٤", "٠٥\u200f/٠٣\u200f/٢٠٢٤", "٢:٣٠ م", " ", " "),
        ("ur", "5 مارچ، 2024", "5/3/24", "2:30 شام", " ", " "),
        # Django 4.2 has neither Uyghur format patterns nor translated month names.
        ("ug", "5-March، 2024", "2024-03-05", "14:30", " ", " ")
        if django.VERSION < (5, 0)
        else ("ug", "5 مارت 2024", "2024/03/05", "14:30", " ", " "),
        ("fa", "۵ مارس ۲۰۲۴", "۲۰۲۴/۳/۵", "۱۴:۳۰", "، ساعت ", "،\u200f "),
        ("he", "5 במרץ 2024", "05/03/2024", "14:30", " ", " "),
        ("en", "March 5, 2024", "03/05/2024", "2:30 p.m.", ", ", " "),
    ],
    ids=["ar", "ar-eg", "ur", "ug", "fa", "he", "en"],
)
def test_fallback_date_time_styles(language, date, short_date, time, joiner, short_joiner, fmt):
    if fmt == "short":
        date, joiner = short_date, short_joiner
    assert format_date(SAMPLE_DATETIME.date(), fmt, language=language) == date
    assert format_time(SAMPLE_DATETIME.time(), fmt, language=language) == time
    assert format_datetime(SAMPLE_DATETIME, fmt, language=language) == date + joiner + time


@override_settings(RTL_ADMIN={"USE_BABEL": False}, FORMAT_MODULE_PATH="project_formats")
@pytest.mark.parametrize(
    ("language", "explicit_key", "regular", "short"),
    [
        ("ar", "SHORT_DATETIME_FORMAT", "2024.03.05 14-30-09", "03/05/2024 2:30 م"),
        ("ur", "DATETIME_FORMAT", "مارچ 5, 2024, 2:30 شام", "5/3/24 14-30-09"),
    ],
)
def test_partial_project_formats_compose_only_missing_datetimes(
    monkeypatch, language, explicit_key, regular, short
):
    module = ModuleType(f"project_formats.{language}.formats")
    module.DATE_FORMAT = "Y.m.d"
    module.TIME_FORMAT = "H-i-s"
    # A genuine locale format can have exactly the same value as the global default.
    setattr(module, explicit_key, getattr(global_settings, explicit_key))
    monkeypatch.setitem(sys.modules, module.__name__, module)
    formats.reset_format_cache()
    try:
        assert format_date(SAMPLE_DATETIME.date(), language=language) == "2024.03.05"
        assert format_time(SAMPLE_DATETIME.time(), language=language) == "14-30-09"
        assert format_datetime(SAMPLE_DATETIME, "medium", language=language) == regular
        assert format_datetime(SAMPLE_DATETIME, "short", language=language) == short
    finally:
        formats.reset_format_cache()


@override_settings(RTL_ADMIN={"USE_BABEL": False}, DATETIME_FORMAT="Y.m.d H:i")
def test_fallback_keeps_django_defaults_for_a_locale_without_data():
    assert format_datetime(SAMPLE_DATETIME, language="zz-zz") == "2024.03.05 14:30"


@override_settings(RTL_ADMIN={"NUMERALS": "arabext"})
def test_custom_and_composed_patterns_respect_numerals_without_babel(monkeypatch):
    monkeypatch.setattr(formatting, "HAS_BABEL", False)
    assert format_datetime(SAMPLE_DATETIME, "short", language="ur") == "۵/۳/۲۴ ۲:۳۰ شام"
    assert format_date(SAMPLE_DATETIME.date(), "Y-m-d", language="en") == "۲۰۲۴-۰۳-۰۵"
    assert format_time(SAMPLE_DATETIME.time(), "H.i.s", language="en") == "۱۴.۳۰.۰۹"
    assert format_datetime(SAMPLE_DATETIME, "d/m H:i:s", language="en") == "۰۵/۰۳ ۱۴:۳۰:۰۹"


@pytest.mark.parametrize("fmt", ["short", "medium", "long", "full"])
def test_babel_date_time_styles_preserve_localized_babel_output(fmt):
    dates = pytest.importorskip("babel.dates")
    digits = str.maketrans("0123456789", ARABIC_INDIC)
    for helper, babel_helper, value in [
        (format_date, dates.format_date, SAMPLE_DATETIME.date()),
        (format_time, dates.format_time, SAMPLE_DATETIME.time()),
        (format_datetime, dates.format_datetime, SAMPLE_DATETIME),
    ]:
        expected = babel_helper(value, format=fmt, locale="ar_EG").translate(digits)
        assert helper(value, fmt, language="ar-eg") == expected


def test_format_date_localises_digits():
    result = format_date(datetime.date(2024, 3, 5), language="ar-eg")
    assert any(char in result for char in ARABIC_INDIC)
    assert format_date(None) == ""


def test_format_date_for_english_keeps_latin_digits():
    assert "2024" in format_date(datetime.date(2024, 3, 5), language="en")


def test_format_datetime_localises_digits():
    value = datetime.datetime(2024, 3, 5, 14, 30)
    assert any(char in format_datetime(value, language="ar-eg") for char in ARABIC_INDIC)
    assert format_datetime(None) == ""


def test_format_time_localises_digits():
    value = datetime.time(14, 30)
    assert any(char in format_time(value, language="fa") for char in EXTENDED)
    assert format_time(None) == ""


@pytest.mark.parametrize("use_babel", [True, False])
@pytest.mark.parametrize(
    ("language", "expected_day", "expected_time", "utc_time"),
    [
        ("en", "6", "12:30", "10:30"),
        ("ar-eg", "٦", "١٢:٣٠", "١٠:٣٠"),
    ],
)
def test_format_datetime_and_time_convert_aware_datetimes_for_time_zone_setting(
    monkeypatch, use_babel, language, expected_day, expected_time, utc_time
):
    if not use_babel:
        monkeypatch.setattr(formatting, "HAS_BABEL", False)
    value = datetime.datetime(2024, 3, 5, 22, 30, tzinfo=datetime.timezone.utc)
    with override_settings(USE_TZ=True, TIME_ZONE="Africa/Cairo"):
        dt_output = format_datetime(value, language=language)
        time_output = format_time(value, language=language)
    assert expected_day in dt_output
    assert expected_time in dt_output
    assert utc_time not in dt_output
    assert expected_time in time_output
    assert utc_time not in time_output


@pytest.mark.parametrize("use_babel", [True, False])
@pytest.mark.parametrize(
    ("language", "expected_day", "expected_time", "utc_time"),
    [
        ("en", "6", "12:30", "10:30"),
        ("ar-eg", "٦", "١٢:٣٠", "١٠:٣٠"),
    ],
)
def test_format_datetime_and_time_convert_aware_datetimes_for_timezone_override(
    monkeypatch, use_babel, language, expected_day, expected_time, utc_time
):
    if not use_babel:
        monkeypatch.setattr(formatting, "HAS_BABEL", False)
    value = datetime.datetime(2024, 3, 5, 22, 30, tzinfo=datetime.timezone.utc)
    with timezone.override("Africa/Cairo"):
        dt_output = format_datetime(value, language=language)
        time_output = format_time(value, language=language)
    assert expected_day in dt_output
    assert expected_time in dt_output
    assert utc_time not in dt_output
    assert expected_time in time_output
    assert utc_time not in time_output


@pytest.mark.parametrize("use_babel", [True, False])
@pytest.mark.parametrize(
    ("language", "expected_day", "expected_time"),
    [
        ("en", "5", "10:30"),
        ("ar-eg", "٥", "١٠:٣٠"),
    ],
)
def test_format_helpers_leave_naive_values_and_plain_dates_untouched(
    monkeypatch, use_babel, language, expected_day, expected_time
):
    if not use_babel:
        monkeypatch.setattr(formatting, "HAS_BABEL", False)
    naive_dt = datetime.datetime(2024, 3, 5, 22, 30)
    naive_time = datetime.time(22, 30)
    plain_date = datetime.date(2024, 3, 5)
    with (
        override_settings(USE_TZ=True, TIME_ZONE="Africa/Cairo"),
        timezone.override("Africa/Cairo"),
    ):
        dt_output = format_datetime(naive_dt, language=language)
        time_output = format_time(naive_time, language=language)
        date_output = format_date(plain_date, language=language)
    assert expected_day in dt_output
    assert expected_time in dt_output
    assert expected_time in time_output
    assert expected_day in date_output


@pytest.mark.parametrize("use_babel", [True, False])
@pytest.mark.parametrize(
    ("language", "expected_day", "expected_time", "cairo_time"),
    [
        ("en", "5", "10:30", "12:30"),
        ("ar-eg", "٥", "١٠:٣٠", "١٢:٣٠"),
    ],
)
def test_format_datetime_and_time_leave_aware_datetimes_untouched_when_use_tz_is_false(
    monkeypatch, use_babel, language, expected_day, expected_time, cairo_time
):
    if not use_babel:
        monkeypatch.setattr(formatting, "HAS_BABEL", False)
    value = datetime.datetime(2024, 3, 5, 22, 30, tzinfo=datetime.timezone.utc)
    with override_settings(USE_TZ=False, TIME_ZONE="Africa/Cairo"):
        dt_output = format_datetime(value, language=language)
        time_output = format_time(value, language=language)
    assert expected_day in dt_output
    assert expected_time in dt_output
    assert cairo_time not in dt_output
    assert expected_time in time_output
    assert cairo_time not in time_output


def test_unknown_locale_does_not_blow_up():
    assert format_number(1234, language="zz-zz") != ""


# -- durations and file sizes ---------------------------------------------


@pytest.mark.parametrize("use_babel", [True, False])
@pytest.mark.parametrize(
    ("language", "digits"),
    [
        ("en", "0123456789"),
        ("ar", "0123456789"),
        ("ar-eg", ARABIC_INDIC),
        ("fa", EXTENDED),
    ],
)
def test_format_timedelta_localizes_digits(use_babel, language, digits):
    with override_settings(RTL_ADMIN={"USE_BABEL": use_babel}):
        output = format_timedelta(45, language=language)
    assert any(char in output for char in digits)
    if digits != "0123456789":
        assert all(char not in output for char in "0123456789")


@pytest.mark.parametrize("use_babel", [True, False])
@pytest.mark.parametrize(
    ("language", "digits"),
    [("en", "0123456789"), ("ar", "0123456789"), ("ar-eg", ARABIC_INDIC), ("fa", EXTENDED)],
)
def test_format_filesize_localizes_digits(use_babel, language, digits):
    with override_settings(RTL_ADMIN={"USE_BABEL": use_babel}):
        output = format_filesize(1_500, language=language)
    assert any(char in output for char in digits)
    if digits != "0123456789":
        assert all(char not in output for char in "0123456789")


def test_format_timedelta_accepts_timedeltas_and_seconds():
    assert format_timedelta(datetime.timedelta(minutes=2), language="en") == "2 minutes"
    assert format_timedelta(120, language="en") == "2 minutes"


@pytest.mark.parametrize("use_babel", [True, False])
def test_format_timedelta_honours_granularity_and_add_direction(use_babel):
    with override_settings(RTL_ADMIN={"USE_BABEL": use_babel}):
        assert format_timedelta(90, granularity="minute", language="en") == "2 minutes"
        assert format_timedelta(-45, add_direction=True, language="en").endswith("ago")
        assert not format_timedelta(45, add_direction=True, language="en").endswith("ago")
        assert "45" in format_timedelta(45, add_direction=True, language="en")


@pytest.mark.skipif(not formatting.HAS_BABEL, reason="Babel is not installed")
def test_format_timedelta_matches_babel_when_available():
    assert format_timedelta(45, language="en") == "45 seconds"
    assert format_timedelta(datetime.timedelta(hours=3), format="short", language="en") == "3 hr"
    assert (
        format_timedelta(datetime.timedelta(hours=23), threshold=1.1, language="en") == "23 hours"
    )


def test_fallback_timedelta_uses_english_units(monkeypatch):
    monkeypatch.setattr(formatting, "HAS_BABEL", False)
    assert formatting.format_timedelta(45, language="en") == "45 seconds"
    assert formatting.format_timedelta(3600, language="en") == "1 hour"
    assert formatting.format_timedelta(-45, add_direction=True, language="en") == "45 seconds ago"


def test_format_timedelta_respects_numbering_system_and_language():
    with override_settings(RTL_ADMIN={"NUMERALS": "latn"}):
        assert "1" in formatting.format_timedelta(10, language="ar-eg")
    with override_settings(RTL_ADMIN={"NUMERALS": "arab"}):
        assert any(char in formatting.format_timedelta(10, language="en") for char in ARABIC_INDIC)


@pytest.mark.parametrize("use_babel", [True, False])
def test_duration_and_filesize_honour_an_explicit_language(use_babel):
    with (
        override_settings(RTL_ADMIN={"USE_BABEL": use_babel}),
        translation.override("en"),
    ):
        assert any(char in format_timedelta(5, language="ar-eg") for char in ARABIC_INDIC)
        assert any(char in format_filesize(1500, language="fa") for char in EXTENDED)


def test_format_filesize_uses_decimal_and_binary_units():
    assert formatting.format_filesize(1000, language="en").startswith("1.0")
    assert formatting.format_filesize(1024, binary=True, language="en").startswith("1.0")
    assert formatting.format_filesize(1000, binary=True, language="en").startswith("1000")
    assert formatting.format_filesize(-1500, language="en").startswith("-1.5")


def test_format_filesize_accepts_numeric_strings_and_decimals():
    assert formatting.format_filesize("1500", language="en") == formatting.format_filesize(
        decimal.Decimal("1500"), language="en"
    )


@pytest.mark.parametrize("value", [None, ""])
def test_duration_and_filesize_of_empty_values_are_empty(value):
    assert format_timedelta(value) == ""
    assert format_filesize(value) == ""


@pytest.mark.parametrize("use_babel", [True, False])
@pytest.mark.parametrize(
    "value",
    [
        "abc",
        [],
        {},
        float("nan"),
        float("inf"),
        float("-inf"),
        decimal.Decimal("NaN"),
        decimal.Decimal("Infinity"),
        "NaN",
        "Infinity",
        "-Infinity",
    ],
)
def test_format_timedelta_rejects_non_numeric_input(monkeypatch, use_babel, value):
    if not use_babel:
        monkeypatch.setattr(formatting, "HAS_BABEL", False)
    with pytest.raises(ValueError, match="Timedelta value must be numeric"):
        format_timedelta(value)


@pytest.mark.parametrize("use_babel", [True, False])
@pytest.mark.parametrize(
    "value",
    [
        "abc",
        [],
        {},
        float("nan"),
        float("inf"),
        float("-inf"),
        decimal.Decimal("NaN"),
        decimal.Decimal("Infinity"),
        "NaN",
        "Infinity",
        "-Infinity",
    ],
)
def test_format_filesize_rejects_non_numeric_input(use_babel, value):
    with override_settings(RTL_ADMIN={"USE_BABEL": use_babel}):
        with pytest.raises(ValueError, match="File size value must be numeric"):
            format_filesize(value)


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        (0, "٠ ثانية"),
        (1, "ثانية"),
        (2, "ثانيتان"),
        (5, "٥ ثوان"),
        (45, "٤٥ ثانية"),
    ],
)
def test_no_babel_seconds_follow_arabic_plural_forms(monkeypatch, amount, expected):
    monkeypatch.setattr(formatting, "HAS_BABEL", False)
    assert format_timedelta(amount, language="ar-eg") == expected


def test_filesize_scales_to_the_largest_unit():
    assert format_filesize(10**9, language="en").endswith("GB")
    assert format_filesize(10**15, language="en").endswith("PB")
    assert format_filesize(10**18, language="en").endswith("PB")


def test_no_babel_arabic_direction_precedes_the_duration(monkeypatch):
    monkeypatch.setattr(formatting, "HAS_BABEL", False)
    assert format_timedelta(-45, add_direction=True, language="ar-eg") == "منذ ٤٥ ثانية"
    assert format_timedelta(45, add_direction=True, language="ar-eg") == "خلال ٤٥ ثانية"


@pytest.mark.parametrize(
    ("seconds", "add_direction", "expected"),
    [
        (2, False, "ثانيتان"),
        (-2, True, "منذ ثانيتين"),
        (2, True, "خلال ثانيتين"),
        (-1, True, "منذ ثانية واحدة"),
        (-5, True, "منذ ٥ ثوانٍ"),
    ],
)
def test_no_babel_arabic_dual_seconds_take_no_number(monkeypatch, seconds, add_direction, expected):
    monkeypatch.setattr(formatting, "HAS_BABEL", False)
    assert format_timedelta(seconds, add_direction=add_direction, language="ar-eg") == expected


@pytest.mark.parametrize(
    ("seconds", "plain", "past", "future"),
    [
        (120, "دقيقتان", "منذ دقيقتين", "خلال دقيقتين"),
        (7_200, "ساعتان", "منذ ساعتين", "خلال ساعتين"),
        (3_600, "ساعة", "منذ ساعة واحدة", "خلال ساعة واحدة"),
        (172_800, "يومان", "منذ يومين", "خلال يومين"),
        (28_512_000, "١١ شهرًا", "منذ ١١ شهرًا", "خلال ١١ شهرًا"),
        (1_209_600, "أسبوعان", "منذ أسبوعين", "خلال أسبوعين"),
        (5_184_000, "شهران", "منذ شهرين", "خلال شهرين"),
        (63_072_000, "سنتان", "منذ سنتين", "خلال سنتين"),
        (94_608_000, "٣ سنوات", "منذ ٣ سنوات", "خلال ٣ سنوات"),
    ],
)
def test_no_babel_arabic_units_use_the_package_wording(monkeypatch, seconds, plain, past, future):
    monkeypatch.setattr(formatting, "HAS_BABEL", False)
    kwargs = {"threshold": 1, "language": "ar-eg"}
    assert format_timedelta(seconds, **kwargs) == plain
    assert format_timedelta(-seconds, add_direction=True, **kwargs) == past
    assert format_timedelta(seconds, add_direction=True, **kwargs) == future


@pytest.mark.skipif(not formatting.HAS_BABEL, reason="Babel is not installed")
@pytest.mark.parametrize("seconds", [2, 120, 7_200, 172_800, 1_209_600, 5_184_000, 63_072_000])
def test_no_babel_arabic_duals_match_babel(monkeypatch, seconds):
    with_babel = format_timedelta(seconds, threshold=1, language="ar-eg")
    future = format_timedelta(seconds, threshold=1, add_direction=True, language="ar-eg")
    monkeypatch.setattr(formatting, "HAS_BABEL", False)
    assert format_timedelta(seconds, threshold=1, language="ar-eg") == with_babel
    assert format_timedelta(seconds, threshold=1, add_direction=True, language="ar-eg") == future


def test_no_babel_other_languages_keep_django_units(monkeypatch):
    monkeypatch.setattr(formatting, "HAS_BABEL", False)
    assert format_timedelta(120, language="en") == "2 minutes"
    assert format_timedelta(-120, add_direction=True, language="en") == "2 minutes ago"
    assert format_timedelta(-2, add_direction=True, language="he") == "לפני 2 שניות"
    assert format_timedelta(-120, add_direction=True, language="he") == "לפני 2 דקות"


@pytest.mark.parametrize("use_babel", [True, False])
@pytest.mark.parametrize(
    ("language", "expected"),
    [
        ("en", "-2.0\xa0KB"),
        ("ar-eg", "\u061c-٢٫٠\xa0ك.ب"),
        ("fa", "\u200e\u2212۲٫۰\xa0کیلوبایت"),
    ],
)
def test_negative_file_sizes_use_the_locale_minus_sign(use_babel, language, expected):
    with override_settings(RTL_ADMIN={"USE_BABEL": use_babel}):
        assert format_filesize(-2_000, language=language) == expected


def test_minus_sign_falls_back_to_cldr_without_babel(monkeypatch):
    monkeypatch.setattr(formatting, "HAS_BABEL", False)
    assert formatting._minus_sign("ar-eg") == "\u061c-"
    assert formatting._minus_sign("fa") == "\u200e\u2212"
    assert formatting._minus_sign("ar") == "-"
    assert formatting._minus_sign("en") == "-"


@pytest.mark.parametrize("use_babel", [True, False])
@pytest.mark.parametrize(
    ("num_bytes", "expected"),
    [
        (1_500, "۱٫۵\xa0کیلوبایت"),
        (1_500_000, "۱٫۵\xa0مگابایت"),
        (931_300_000_000, "۹۳۱٫۳\xa0گیگابایت"),
        (2 * 10**12, "۲٫۰\xa0ترابایت"),
        (2 * 10**15, "۲٫۰\xa0پتابایت"),
    ],
)
def test_persian_file_size_units_are_translated(use_babel, num_bytes, expected):
    with override_settings(RTL_ADMIN={"USE_BABEL": use_babel}):
        assert format_filesize(num_bytes, language="fa") == expected


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        ("he", '2.0\xa0ק"ב'),
        ("fa", "2.0\xa0KB"),
        ("ar", "2,0\xa0ك.ب"),
    ],
)
def test_django_filesizeformat_is_unchanged_by_the_package_catalogs(language, expected):
    from django.template.defaultfilters import filesizeformat

    with translation.override(language):
        assert filesizeformat(2_048) == expected


def test_a_language_the_package_does_not_ship_uses_django_units():
    assert format_filesize(2_000, language="de") == "2,0\xa0KB"
