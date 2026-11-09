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
    assert numbering_system("fa") == "arabext"
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


def test_format_number_falls_back_to_django_without_babel(monkeypatch):
    monkeypatch.setattr(formatting, "HAS_BABEL", False)
    result = format_number(1234, language="ar-eg")
    assert any(char in result for char in ARABIC_INDIC)


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
