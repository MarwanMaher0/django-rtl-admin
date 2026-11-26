"""Umm al-Qura Hijri calendar conversion.

The Umm al-Qura calendar is the civil calendar of Saudi Arabia.  Its month
lengths come from an official table rather than from an arithmetic rule, so
this module embeds the month-start table for 1343--1500 AH
(1924-08-01--2077-11-16 CE) instead of depending on Babel, ICU or another
calendar library.

The table holds the Reduced Julian Day number (RJD) of the first day of every
supported Hijri month, followed by the start of the month after Dhu al-Hijjah
1500.  It follows the Umm al-Qura calendar published by the Institute of
Astronomical and Geophysical Research at King Abdulaziz City for Science and
Technology (KACST), in the layout used by the MIT-licensed ``hijridate``
project.
"""

from __future__ import annotations

import datetime
from bisect import bisect_right
from dataclasses import dataclass
from itertools import accumulate

from django.conf import settings
from django.utils import timezone

#: First and last Hijri years covered by the embedded table.
MIN_YEAR = 1343
MAX_YEAR = 1500

#: First and last Gregorian dates covered by the embedded table.
MIN_DATE = datetime.date(1924, 8, 1)
MAX_DATE = datetime.date(2077, 11, 16)

MONTHS_PER_YEAR = 12

# ``date.toordinal()`` minus the RJD of the same day.  RJD = JDN - 2400000
# and the proleptic Gregorian ordinal is JDN - 1721425.
_ORDINAL_OFFSET = 678575

#: RJD of the first supported day, 1924-08-01 (1343-01-01 AH).
_FIRST_RJD = 23999

#: One character per supported month, encoding ``month_length - 28`` as a
#: digit: ``0`` = 28, ``1`` = 29, ``2`` = 30, ``3`` = 31.  The official table
#: has 1896 months; historical corrections make a few of them 28 or 31 days.
_MONTH_LENGTHS_DATA = (
    "21221222022211212121212121213120221211221221122111221221221121212122113021212122"
    "20321212112122122121211122122121212121212122121221121212122121212121212122121121"
    "21221121212121212122221211211221222121121121212121212122212121212121212121212121"
    "21212121212221212120222121212121212221212121212121212121212121212121212221212122"
    "12212121212121212121121212221212121121221212121212122121212211222121212112211211"
    "22212121211212122122212121212121121212121212212121212121212212112121212212211212"
    "12122121212121212121212121221121222122112121212211212121212212212121212121212121"
    "21222121212212112121212121221121212121222121112121222121212112212122121121212122"
    "21211212121221212121212121221212121212121221221211212122121212112121222121211212"
    "12221212112112212221211211221221212121212121221212121212121221212121121221221212"
    "11212122212121121212212212112112212221211211221221221121121222121212112122122121"
    "21211212212122121211212122212121121212212212121121222212112111222212211211122212"
    "21212112121221221211212121221212212112121221221211212122122121121122212212112112"
    "21221221121212121221212121121222121212112122122121211212122122112121212122121212"
    "12121212212211212112212221121121212221212112121222121211212122122121121212122121"
    "21212121212212122112121212221211211212221221121121222121212112122122121211212122"
    "12212121121212212212112121212221211212121222112121211222121212121122121221212112"
    "12122212121121122122212112112212221211211221221212121122121221212121212121212212"
    "12112122122121211212122212121121122221212112121221221211212121221212121211221221"
    "22112112212122211211212212212121211212212122121121212212212112121212221211211212"
    "22122112112122122211211212212212121121212212122112121212122122121121212212212112"
    "11221222121121122122122112112212122211212121212212121211212212212121121212221212"
    "11212122122121121212122121221121212122122112121122122211211212122212121121212221"
    "21211212122122112121212122121212121212121221221121121222"
)

_MONTH_LENGTHS = tuple(28 + int(char) for char in _MONTH_LENGTHS_DATA)
# 1896 month starts plus the sentinel start of the month after 1500-12.
_MONTH_STARTS: tuple[int, ...] = tuple(accumulate(_MONTH_LENGTHS, initial=_FIRST_RJD))
_END_RJD = _MONTH_STARTS[-1]


_RANGE_TEXT = (
    "the supported Umm al-Qura range 1343-1500 AH (1924-2077 CE): "
    "1343-01-01 to 1500-12-30 AH (1924-08-01 to 2077-11-16 CE)"
)

#: Full month names used by :func:`django_rtl_admin.formatting.format_hijri_date`.
#: Arabic, Persian and Urdu use their own spellings; every other language gets
#: an English transliteration.
MONTH_NAMES: dict[str, tuple[str, ...]] = {
    "ar": (
        "محرم",
        "صفر",
        "ربيع الأول",
        "ربيع الآخر",
        "جمادى الأولى",
        "جمادى الآخرة",
        "رجب",
        "شعبان",
        "رمضان",
        "شوال",
        "ذو القعدة",
        "ذو الحجة",
    ),
    "fa": (
        "محرم",
        "صفر",
        "ربیع‌الاول",
        "ربیع‌الثانی",
        "جمادی‌الاول",
        "جمادی‌الثانی",
        "رجب",
        "شعبان",
        "رمضان",
        "شوال",
        "ذی‌القعده",
        "ذی‌الحجه",
    ),
    "ur": (
        "محرم",
        "صفر",
        "ربیع الاول",
        "ربیع الثانی",
        "جمادی الاول",
        "جمادی الثانی",
        "رجب",
        "شعبان",
        "رمضان",
        "شوال",
        "ذو القعدہ",
        "ذو الحجہ",
    ),
    "en": (
        "Muharram",
        "Safar",
        "Rabi' al-Awwal",
        "Rabi' al-Thani",
        "Jumada al-Ula",
        "Jumada al-Akhirah",
        "Rajab",
        "Sha'ban",
        "Ramadan",
        "Shawwal",
        "Dhu al-Qi'dah",
        "Dhu al-Hijjah",
    ),
}

#: Era suffix appended by ``format_hijri_date(..., suffix=True)``.
ERA_SUFFIXES: dict[str, str] = {
    "ar": "هـ",
    "fa": "هجری قمری",
    "ur": "ہجری",
    "en": "AH",
}


@dataclass(frozen=True)
class HijriDate:
    """A date in the Umm al-Qura Hijri calendar."""

    year: int
    month: int
    day: int
    month_length: int


def _to_rjd(value: datetime.date | datetime.datetime) -> int:
    """Return the Reduced Julian Day number for a Gregorian date.

    Aware datetimes are converted to Django's current time zone first, exactly
    like the other date/time helpers; naive datetimes and plain dates keep the
    calendar day they already carry.
    """
    if isinstance(value, datetime.datetime):
        if settings.USE_TZ and timezone.is_aware(value):
            value = timezone.localtime(value)
        value = value.date()
    elif not isinstance(value, datetime.date):
        raise TypeError(f"Expected a date or datetime, got {type(value).__name__}.")

    rjd = value.toordinal() - _ORDINAL_OFFSET
    if not _FIRST_RJD <= rjd < _END_RJD:
        raise ValueError(f"Date {value.isoformat()} is outside {_RANGE_TEXT}.")
    return rjd


def to_hijri(value: datetime.date | datetime.datetime) -> HijriDate:
    """Convert a Gregorian date or datetime to an Umm al-Qura Hijri date.

    ``value`` may be a :class:`datetime.date` or :class:`datetime.datetime`.
    Aware datetimes are converted to the current time zone when ``USE_TZ`` is
    enabled.  Dates outside 1924-08-01--2077-11-16 raise :class:`ValueError`.
    """
    rjd = _to_rjd(value)
    index = bisect_right(_MONTH_STARTS, rjd) - 1
    year = MIN_YEAR + index // MONTHS_PER_YEAR
    month = index % MONTHS_PER_YEAR + 1
    day = rjd - _MONTH_STARTS[index] + 1
    month_length = _MONTH_STARTS[index + 1] - _MONTH_STARTS[index]
    return HijriDate(year=year, month=month, day=day, month_length=month_length)


def from_hijri(year: int, month: int, day: int) -> datetime.date:
    """Convert an Umm al-Qura Hijri date to a Gregorian :class:`datetime.date`.

    The year must be between 1343 and 1500, the month between 1 and 12, and the
    day must exist in that month.  Values outside the supported range raise
    :class:`ValueError` naming the range.
    """
    if not MIN_YEAR <= year <= MAX_YEAR:
        raise ValueError(f"Hijri year {year} is outside {_RANGE_TEXT}.")
    if not 1 <= month <= MONTHS_PER_YEAR:
        raise ValueError(f"Month must be in 1..{MONTHS_PER_YEAR} for {_RANGE_TEXT}.")

    index = (year - MIN_YEAR) * MONTHS_PER_YEAR + month - 1
    month_length = _MONTH_STARTS[index + 1] - _MONTH_STARTS[index]
    if not 1 <= day <= month_length:
        raise ValueError(
            f"Day must be in 1..{month_length} for Hijri month {month} of year {year}."
        )

    rjd = _MONTH_STARTS[index] + day - 1
    return datetime.date.fromordinal(rjd + _ORDINAL_OFFSET)
