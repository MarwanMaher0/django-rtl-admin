"""Umm al-Qura Hijri conversion, formatting and template filter."""

import dataclasses
import datetime

import pytest
from django.template import Context, Template
from django.test import override_settings
from django.utils import timezone, translation

import django_rtl_admin
from django_rtl_admin import (
    HijriDate,
    format_hijri_date,
    formatting,
    from_hijri,
    to_hijri,
)
from django_rtl_admin.formatting import DIGITS

# (Gregorian date, (Hijri year, month, day, month length))
# Checked against the official Umm al-Qura calendar table for 1343--1500 AH.
REFERENCE_DATES = [
    (datetime.date(1924, 8, 1), (1343, 1, 1, 30)),
    (datetime.date(1924, 8, 31), (1343, 2, 1, 29)),
    (datetime.date(1924, 9, 29), (1343, 3, 1, 30)),
    (datetime.date(1924, 10, 29), (1343, 4, 1, 30)),
    (datetime.date(1924, 11, 28), (1343, 5, 1, 29)),
    (datetime.date(1924, 12, 27), (1343, 6, 1, 30)),
    (datetime.date(1925, 1, 26), (1343, 7, 1, 30)),
    (datetime.date(1925, 2, 25), (1343, 8, 1, 30)),
    (datetime.date(1925, 3, 27), (1343, 9, 1, 28)),
    (datetime.date(1925, 4, 24), (1343, 10, 1, 30)),
    (datetime.date(1925, 5, 24), (1343, 11, 1, 30)),
    (datetime.date(1925, 6, 23), (1343, 12, 1, 30)),
    (datetime.date(1941, 1, 28), (1360, 1, 1, 30)),
    (datetime.date(1941, 2, 27), (1360, 2, 1, 29)),
    (datetime.date(1941, 3, 28), (1360, 3, 1, 30)),
    (datetime.date(1941, 4, 27), (1360, 4, 1, 29)),
    (datetime.date(1941, 5, 26), (1360, 5, 1, 30)),
    (datetime.date(1941, 6, 25), (1360, 6, 1, 29)),
    (datetime.date(1941, 7, 24), (1360, 7, 1, 30)),
    (datetime.date(1941, 8, 23), (1360, 8, 1, 29)),
    (datetime.date(1941, 9, 21), (1360, 9, 1, 30)),
    (datetime.date(1941, 10, 21), (1360, 10, 1, 29)),
    (datetime.date(1941, 11, 19), (1360, 11, 1, 30)),
    (datetime.date(1941, 12, 19), (1360, 12, 1, 30)),
    (datetime.date(1960, 6, 25), (1380, 1, 1, 30)),
    (datetime.date(1960, 7, 25), (1380, 2, 1, 29)),
    (datetime.date(1960, 8, 23), (1380, 3, 1, 30)),
    (datetime.date(1960, 9, 22), (1380, 4, 1, 29)),
    (datetime.date(1960, 10, 21), (1380, 5, 1, 30)),
    (datetime.date(1960, 11, 20), (1380, 6, 1, 29)),
    (datetime.date(1960, 12, 19), (1380, 7, 1, 30)),
    (datetime.date(1961, 1, 18), (1380, 8, 1, 29)),
    (datetime.date(1961, 2, 16), (1380, 9, 1, 30)),
    (datetime.date(1961, 3, 18), (1380, 10, 1, 29)),
    (datetime.date(1961, 4, 16), (1380, 11, 1, 30)),
    (datetime.date(1961, 5, 16), (1380, 12, 1, 29)),
    (datetime.date(1979, 11, 20), (1400, 1, 1, 30)),
    (datetime.date(1979, 12, 20), (1400, 2, 1, 30)),
    (datetime.date(1980, 1, 19), (1400, 3, 1, 29)),
    (datetime.date(1980, 2, 17), (1400, 4, 1, 30)),
    (datetime.date(1980, 3, 18), (1400, 5, 1, 29)),
    (datetime.date(1980, 4, 16), (1400, 6, 1, 29)),
    (datetime.date(1980, 5, 15), (1400, 7, 1, 30)),
    (datetime.date(1980, 6, 14), (1400, 8, 1, 29)),
    (datetime.date(1980, 7, 13), (1400, 9, 1, 30)),
    (datetime.date(1980, 8, 12), (1400, 10, 1, 29)),
    (datetime.date(1980, 9, 10), (1400, 11, 1, 30)),
    (datetime.date(1980, 10, 10), (1400, 12, 1, 30)),
    (datetime.date(1999, 4, 17), (1420, 1, 1, 29)),
    (datetime.date(1999, 5, 16), (1420, 2, 1, 30)),
    (datetime.date(1999, 6, 15), (1420, 3, 1, 29)),
    (datetime.date(1999, 7, 14), (1420, 4, 1, 29)),
    (datetime.date(1999, 8, 12), (1420, 5, 1, 30)),
    (datetime.date(1999, 9, 11), (1420, 6, 1, 29)),
    (datetime.date(1999, 10, 10), (1420, 7, 1, 30)),
    (datetime.date(1999, 11, 9), (1420, 8, 1, 30)),
    (datetime.date(1999, 12, 9), (1420, 9, 1, 30)),
    (datetime.date(2000, 1, 8), (1420, 10, 1, 30)),
    (datetime.date(2000, 2, 7), (1420, 11, 1, 29)),
    (datetime.date(2000, 3, 7), (1420, 12, 1, 30)),
    (datetime.date(2018, 9, 11), (1440, 1, 1, 29)),
    (datetime.date(2018, 10, 10), (1440, 2, 1, 30)),
    (datetime.date(2018, 11, 9), (1440, 3, 1, 29)),
    (datetime.date(2018, 12, 8), (1440, 4, 1, 30)),
    (datetime.date(2019, 1, 7), (1440, 5, 1, 30)),
    (datetime.date(2019, 2, 6), (1440, 6, 1, 30)),
    (datetime.date(2019, 3, 8), (1440, 7, 1, 29)),
    (datetime.date(2019, 4, 6), (1440, 8, 1, 30)),
    (datetime.date(2019, 5, 6), (1440, 9, 1, 29)),
    (datetime.date(2019, 6, 4), (1440, 10, 1, 30)),
    (datetime.date(2019, 7, 4), (1440, 11, 1, 29)),
    (datetime.date(2019, 8, 2), (1440, 12, 1, 29)),
    (datetime.date(2023, 7, 19), (1445, 1, 1, 29)),
    (datetime.date(2023, 8, 17), (1445, 2, 1, 30)),
    (datetime.date(2023, 9, 16), (1445, 3, 1, 30)),
    (datetime.date(2023, 10, 16), (1445, 4, 1, 30)),
    (datetime.date(2023, 11, 15), (1445, 5, 1, 29)),
    (datetime.date(2023, 12, 14), (1445, 6, 1, 30)),
    (datetime.date(2024, 1, 13), (1445, 7, 1, 29)),
    (datetime.date(2024, 2, 11), (1445, 8, 1, 29)),
    (datetime.date(2024, 3, 11), (1445, 9, 1, 30)),
    (datetime.date(2024, 4, 10), (1445, 10, 1, 29)),
    (datetime.date(2024, 5, 9), (1445, 11, 1, 29)),
    (datetime.date(2024, 6, 7), (1445, 12, 1, 30)),
    (datetime.date(2028, 5, 25), (1450, 1, 1, 30)),
    (datetime.date(2028, 6, 24), (1450, 2, 1, 29)),
    (datetime.date(2028, 7, 23), (1450, 3, 1, 30)),
    (datetime.date(2028, 8, 22), (1450, 4, 1, 29)),
    (datetime.date(2028, 9, 20), (1450, 5, 1, 29)),
    (datetime.date(2028, 10, 19), (1450, 6, 1, 30)),
    (datetime.date(2028, 11, 18), (1450, 7, 1, 29)),
    (datetime.date(2028, 12, 17), (1450, 8, 1, 30)),
    (datetime.date(2029, 1, 16), (1450, 9, 1, 29)),
    (datetime.date(2029, 2, 14), (1450, 10, 1, 30)),
    (datetime.date(2029, 3, 16), (1450, 11, 1, 30)),
    (datetime.date(2029, 4, 15), (1450, 12, 1, 29)),
    (datetime.date(2047, 10, 20), (1470, 1, 1, 30)),
    (datetime.date(2047, 11, 19), (1470, 2, 1, 29)),
    (datetime.date(2047, 12, 18), (1470, 3, 1, 29)),
    (datetime.date(2048, 1, 16), (1470, 4, 1, 30)),
    (datetime.date(2048, 2, 15), (1470, 5, 1, 30)),
    (datetime.date(2048, 3, 16), (1470, 6, 1, 29)),
    (datetime.date(2048, 4, 14), (1470, 7, 1, 30)),
    (datetime.date(2048, 5, 14), (1470, 8, 1, 29)),
    (datetime.date(2048, 6, 12), (1470, 9, 1, 30)),
    (datetime.date(2048, 7, 12), (1470, 10, 1, 30)),
    (datetime.date(2048, 8, 11), (1470, 11, 1, 30)),
    (datetime.date(2048, 9, 10), (1470, 12, 1, 29)),
    (datetime.date(2076, 11, 27), (1500, 1, 1, 30)),
    (datetime.date(2076, 12, 27), (1500, 2, 1, 30)),
    (datetime.date(2077, 1, 26), (1500, 3, 1, 29)),
    (datetime.date(2077, 2, 24), (1500, 4, 1, 29)),
    (datetime.date(2077, 3, 25), (1500, 5, 1, 30)),
    (datetime.date(2077, 4, 24), (1500, 6, 1, 29)),
    (datetime.date(2077, 5, 23), (1500, 7, 1, 29)),
    (datetime.date(2077, 6, 21), (1500, 8, 1, 30)),
    (datetime.date(2077, 7, 21), (1500, 9, 1, 29)),
    (datetime.date(2077, 8, 19), (1500, 10, 1, 30)),
    (datetime.date(2077, 9, 18), (1500, 11, 1, 30)),
    (datetime.date(2077, 10, 18), (1500, 12, 1, 30)),
    (datetime.date(1925, 4, 23), (1343, 9, 28, 28)),
    (datetime.date(1925, 7, 22), (1343, 12, 30, 30)),
    (datetime.date(1980, 8, 11), (1400, 9, 30, 30)),
    (datetime.date(1980, 11, 8), (1400, 12, 30, 30)),
    (datetime.date(2024, 4, 9), (1445, 9, 30, 30)),
    (datetime.date(2024, 7, 6), (1445, 12, 30, 30)),
    (datetime.date(2025, 3, 1), (1446, 9, 1, 29)),
    (datetime.date(2025, 3, 29), (1446, 9, 29, 29)),
    (datetime.date(2025, 5, 28), (1446, 12, 1, 29)),
    (datetime.date(2025, 6, 25), (1446, 12, 29, 29)),
    (datetime.date(2026, 2, 18), (1447, 9, 1, 30)),
    (datetime.date(2026, 3, 19), (1447, 9, 30, 30)),
    (datetime.date(2026, 5, 18), (1447, 12, 1, 29)),
    (datetime.date(2026, 6, 15), (1447, 12, 29, 29)),
    (datetime.date(2077, 8, 18), (1500, 9, 29, 29)),
    (datetime.date(2077, 11, 16), (1500, 12, 30, 30)),
]


@pytest.mark.parametrize(("gregorian", "hijri"), REFERENCE_DATES)
def test_reference_dates_match_the_official_umm_al_qura_calendar(gregorian, hijri):
    result = to_hijri(gregorian)
    assert (result.year, result.month, result.day, result.month_length) == hijri
    assert from_hijri(*hijri[:3]) == gregorian


def test_reference_set_covers_the_whole_range_and_both_month_lengths():
    gregorian_dates = {gregorian for gregorian, _ in REFERENCE_DATES}
    assert datetime.date(1924, 8, 1) in gregorian_dates
    assert datetime.date(2077, 11, 16) in gregorian_dates
    lengths = {hijri[3] for _, hijri in REFERENCE_DATES}
    assert {29, 30} <= lengths
    months = {hijri[1] for _, hijri in REFERENCE_DATES}
    assert {9, 12} <= months
    years = {hijri[0] for _, hijri in REFERENCE_DATES}
    assert min(years) == 1343
    assert max(years) == 1500


def test_the_first_and_last_supported_days_round_trip():
    first = to_hijri(datetime.date(1924, 8, 1))
    assert first == HijriDate(1343, 1, 1, first.month_length)
    assert (first.year, first.month, first.day) == (1343, 1, 1)
    assert first.month_length == 30

    last = to_hijri(datetime.date(2077, 11, 16))
    assert (last.year, last.month, last.day, last.month_length) == (1500, 12, 30, 30)
    assert from_hijri(1343, 1, 1) == datetime.date(1924, 8, 1)
    assert from_hijri(1500, 12, 30) == datetime.date(2077, 11, 16)


def test_every_supported_day_round_trips():
    day = datetime.date(1924, 8, 1)
    end = datetime.date(2077, 11, 16)
    count = 0
    while day <= end:
        hijri = to_hijri(day)
        assert 1 <= hijri.year <= 1500
        assert 1 <= hijri.month <= 12
        assert 1 <= hijri.day <= hijri.month_length
        assert from_hijri(hijri.year, hijri.month, hijri.day) == day
        day += datetime.timedelta(days=1)
        count += 1
    assert count == (end - datetime.date(1924, 8, 1)).days + 1


def test_hijri_date_is_a_frozen_dataclass():
    hijri = to_hijri(datetime.date(2024, 3, 11))
    assert dataclasses.is_dataclass(hijri)
    assert hijri == HijriDate(hijri.year, hijri.month, hijri.day, hijri.month_length)
    with pytest.raises(dataclasses.FrozenInstanceError):
        hijri.year = 1446


def test_public_helpers_are_exported():
    assert {"HijriDate", "format_hijri_date", "from_hijri", "to_hijri"} <= set(
        django_rtl_admin.__all__
    )
    assert django_rtl_admin.to_hijri is to_hijri
    assert django_rtl_admin.from_hijri is from_hijri
    assert django_rtl_admin.format_hijri_date is formatting.format_hijri_date


@override_settings(USE_TZ=True, TIME_ZONE="Asia/Riyadh")
def test_aware_datetimes_are_converted_to_the_current_time_zone():
    # 22:30 UTC is 01:30 on 11 March in Riyadh: the first day of Ramadan 1445.
    value = datetime.datetime(2024, 3, 10, 22, 30, tzinfo=datetime.timezone.utc)
    hijri = to_hijri(value)
    assert (hijri.year, hijri.month, hijri.day) == (1445, 9, 1)
    assert format_hijri_date(value, language="en") == "1 Ramadan 1445 AH"


@override_settings(USE_TZ=True, TIME_ZONE="Africa/Cairo")
def test_aware_datetimes_follow_a_timezone_override():
    value = datetime.datetime(2024, 3, 10, 22, 30, tzinfo=datetime.timezone.utc)
    with timezone.override("Asia/Riyadh"):
        hijri = to_hijri(value)
    assert (hijri.year, hijri.month, hijri.day) == (1445, 9, 1)


@override_settings(USE_TZ=True, TIME_ZONE="Asia/Riyadh")
def test_naive_datetimes_keep_their_calendar_day():
    naive = datetime.datetime(2024, 3, 10, 22, 30)
    expected = to_hijri(naive.date())
    assert to_hijri(naive) == expected
    assert format_hijri_date(naive, language="en") == format_hijri_date(naive.date(), language="en")


@override_settings(USE_TZ=False, TIME_ZONE="Asia/Riyadh")
def test_aware_datetimes_without_use_tz_keep_their_own_date():
    value = datetime.datetime(2024, 3, 10, 22, 30, tzinfo=datetime.timezone.utc)
    assert to_hijri(value) == to_hijri(datetime.date(2024, 3, 10))


@pytest.mark.parametrize(
    ("language", "month_name", "suffix"),
    [
        ("en", "Ramadan", "AH"),
        ("en-gb", "Ramadan", "AH"),
        ("ar", "رمضان", "هـ"),
        ("ar-eg", "رمضان", "هـ"),
        ("ar-sa", "رمضان", "هـ"),
        ("fa", "رمضان", "هجری قمری"),
        ("fa-ir", "رمضان", "هجری قمری"),
        ("ur", "رمضان", "ہجری"),
        ("ur-pk", "رمضان", "ہجری"),
        ("he", "Ramadan", "AH"),
    ],
)
def test_each_language_uses_its_own_month_names_and_suffix(language, month_name, suffix):
    output = format_hijri_date(datetime.date(2024, 3, 11), language=language)
    digits = DIGITS[formatting.numbering_system(language)]
    assert month_name in output
    assert suffix in output
    assert all(
        char not in output
        for char in "".join(
            DIGITS[key] for key in DIGITS if key != formatting.numbering_system(language)
        )
    )
    assert any(char in output for char in digits)


@pytest.mark.parametrize(
    ("hijri", "language", "english_name", "arabic_name"),
    [
        ((1445, 1, 1), "en", "Muharram", "محرم"),
        ((1445, 3, 1), "en", "Rabi' al-Awwal", "ربيع الأول"),
        ((1445, 6, 1), "en", "Jumada al-Akhirah", "جمادى الآخرة"),
        ((1445, 8, 1), "en", "Sha'ban", "شعبان"),
        ((1445, 9, 1), "en", "Ramadan", "رمضان"),
        ((1445, 11, 1), "en", "Dhu al-Qi'dah", "ذو القعدة"),
        ((1445, 12, 1), "en", "Dhu al-Hijjah", "ذو الحجة"),
    ],
)
def test_full_month_names(hijri, language, english_name, arabic_name):
    gregorian = from_hijri(*hijri)
    assert english_name in format_hijri_date(gregorian, language=language)
    assert arabic_name in format_hijri_date(gregorian, language="ar")


def test_persian_and_urdu_month_names_are_not_english():
    gregorian = from_hijri(1445, 12, 1)
    assert "ذی‌الحجه" in format_hijri_date(gregorian, language="fa")
    assert "ذو الحجہ" in format_hijri_date(gregorian, language="ur")


def test_formats_and_suffix_switch():
    gregorian = datetime.date(2024, 3, 12)  # 2 Ramadan 1445
    assert format_hijri_date(gregorian, language="en") == "2 Ramadan 1445 AH"
    assert format_hijri_date(gregorian, language="en", fmt="long") == "2 Ramadan 1445 AH"
    assert format_hijri_date(gregorian, language="en", fmt="medium") == "02 Ramadan 1445 AH"
    assert format_hijri_date(gregorian, language="en", fmt="short") == "02/09/1445 AH"
    assert format_hijri_date(gregorian, language="en", suffix=False) == "2 Ramadan 1445"
    assert format_hijri_date(gregorian, language="ar-eg", suffix=False) == "٢ رمضان ١٤٤٥"


def test_unknown_format_is_rejected():
    with pytest.raises(ValueError, match="Unknown Hijri date format"):
        format_hijri_date(datetime.date(2024, 3, 11), fmt="full")  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [None, ""])
def test_empty_values_render_empty(value):
    assert format_hijri_date(value) == ""


@pytest.mark.parametrize("system", ["latn", "arab", "arabext"])
@override_settings()
def test_each_numbering_system_is_used(system):
    with override_settings(RTL_ADMIN={"NUMERALS": system}):
        output = format_hijri_date(datetime.date(2024, 3, 11), language="en")
        assert any(char in output for char in DIGITS[system])
        assert all(
            char not in output for key, digits in DIGITS.items() if key != system for char in digits
        )


@override_settings(RTL_ADMIN={"NUMERALS": "latn"})
def test_numbering_system_override_beats_the_language():
    output = format_hijri_date(datetime.date(2024, 3, 11), language="ar-eg")
    assert "1445" in output
    assert not any(char in output for char in DIGITS["arab"])


def render(template, **context):
    return Template("{% load rtl_admin %}" + template).render(Context(context))


def test_hijri_date_filter_in_a_rendered_template():
    with translation.override("ar-eg"):
        output = render("{{ value|hijri_date }}", value=datetime.date(2024, 3, 11))
    assert "رمضان" in output
    assert "١٤٤٥" in output
    assert "هـ" in output


def test_hijri_date_filter_accepts_a_format_argument():
    with translation.override("en"):
        assert render('{{ value|hijri_date:"short" }}', value=datetime.date(2024, 3, 12)) == (
            "02/09/1445 AH"
        )
        assert render('{{ value|hijri_date:"full" }}', value=datetime.date(2024, 3, 12)) == (
            "2 Ramadan 1445 AH"
        )


@pytest.mark.parametrize("value", [None, "2024-03-11", 20240311])
def test_hijri_date_filter_returns_empty_for_invalid_values(value):
    assert render("{{ value|hijri_date }}", value=value) == ""


def test_hijri_date_filter_returns_empty_outside_the_supported_range():
    assert render("{{ value|hijri_date }}", value=datetime.date(1924, 7, 31)) == ""
    assert render("{{ value|hijri_date }}", value=datetime.date(2077, 11, 17)) == ""


@pytest.mark.parametrize(
    "value",
    [datetime.date(1924, 7, 31), datetime.date(2077, 11, 17), datetime.date(1900, 1, 1)],
)
def test_to_hijri_rejects_dates_outside_the_range(value):
    with pytest.raises(
        ValueError,
        match=r"supported Umm al-Qura range 1343-1500 AH \(1924-2077 CE\)",
    ) as excinfo:
        to_hijri(value)
    assert "1924-08-01 to 2077-11-16 CE" in str(excinfo.value)


@pytest.mark.parametrize("year", [1342, 1501, 0, 9999])
def test_from_hijri_rejects_years_outside_the_range(year):
    with pytest.raises(ValueError, match=r"supported Umm al-Qura range"):
        from_hijri(year, 1, 1)


@pytest.mark.parametrize("month", [0, 13, -1])
def test_from_hijri_rejects_invalid_months(month):
    with pytest.raises(ValueError, match=r"Month must be in 1\.\.12"):
        from_hijri(1445, month, 1)


@pytest.mark.parametrize(
    ("year", "month", "day", "length"),
    [
        (1343, 1, 31, 30),
        (1445, 9, 31, 30),
        (1445, 10, 30, 29),
        (1446, 12, 30, 29),
        (1445, 9, 0, 30),
    ],
)
def test_from_hijri_rejects_days_outside_the_month(year, month, day, length):
    with pytest.raises(ValueError, match=rf"Day must be in 1\.\.{length}"):
        from_hijri(year, month, day)


def test_to_hijri_rejects_non_date_values():
    with pytest.raises(TypeError, match="Expected a date or datetime"):
        to_hijri("2024-03-11")  # type: ignore[arg-type]
