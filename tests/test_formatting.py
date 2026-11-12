"""Locale-aware number, date and currency formatting."""

import datetime
import decimal

import pytest
from django.test import override_settings
from django.utils import timezone

from django_rtl_admin import formatting
from django_rtl_admin.formatting import (
    DIGITS,
    format_currency,
    format_date,
    format_datetime,
    format_number,
    format_percent,
    format_time,
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
def test_format_number_uses_cldr_separators_without_babel(
    monkeypatch, language, expected
):
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
    assert (
        format_number(10**20, language="en", decimal_pos=2)
        == "100,000,000,000,000,000,000.00"
    )


BIG_30_DIGITS = decimal.Decimal("123456789012345678901234567890")
BIG_30_DIGITS_EN = "123,456,789,012,345,678,901,234,567,890"
BIG_30_SIG_FIGS = decimal.Decimal("1234567890123456789012345678.915")
BIG_30_SIG_FIGS_EN = "1,234,567,890,123,456,789,012,345,678.915"


@pytest.mark.skipif(not formatting.HAS_BABEL, reason="Babel is not installed")
def test_format_number_keeps_every_digit_of_huge_decimals_with_babel():
    # Babel raises InvalidOperation beyond its context precision, so its
    # fallback renderer handles the value; every digit must survive.
    assert format_number(BIG_30_DIGITS, language="en") == BIG_30_DIGITS_EN
    assert (
        format_number(BIG_30_DIGITS, language="en", decimal_pos=2)
        == BIG_30_DIGITS_EN + ".00"
    )


def test_format_number_without_babel_keeps_every_digit_of_huge_decimals(monkeypatch):
    monkeypatch.setattr(formatting, "HAS_BABEL", False)
    # normalize() runs under the widened context, so values beyond the
    # default 28-digit precision are not rounded; rounding still applies
    # to the fraction at an explicit position, half-to-even.
    assert format_number(BIG_30_DIGITS, language="en") == BIG_30_DIGITS_EN
    assert (
        format_number(BIG_30_DIGITS, language="en", decimal_pos=2)
        == BIG_30_DIGITS_EN + ".00"
    )
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
def test_ungrouped_format_number_matches_babel_without_it_installed(
    monkeypatch, language
):
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
def test_format_currency_rejects_non_numeric_input(
    monkeypatch, use_babel, language, value
):
    if not use_babel:
        monkeypatch.setattr(formatting, "HAS_BABEL", False)
    with pytest.raises(ValueError, match="Currency value must be numeric"):
        format_currency(value, language=language)


def test_format_percent():
    assert format_percent(0.256, language="en").startswith("26")


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
