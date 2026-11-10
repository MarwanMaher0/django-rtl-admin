"""Locale-aware number, date and currency formatting.

Arabic locales do not all agree on how to write a number.  ``ar-EG`` uses
Arabic-Indic digits (``١٢٣``) with U+066C as the group separator and U+066B as
the decimal separator; ``ar-MA`` and plain ``ar`` use Latin digits with the
usual comma and full stop.  Django's ``USE_THOUSAND_SEPARATOR``/``L10N``
machinery has no concept of a numbering system at all, so an Arabic admin ends
up showing Latin digits everywhere no matter what the locale says.

These helpers use `Babel <https://babel.pocoo.org/>`_ when it is installed --
``pip install django-rtl-admin[babel]`` -- and fall back to Django's own
``django.utils.formats`` plus a digit transliteration step when it is not.
Nothing here raises if Babel is missing.
"""

from __future__ import annotations

import contextlib
import datetime
import decimal
from typing import Any

from django.conf import settings
from django.utils import formats, timezone, translation
from django.utils.translation import get_language, to_locale

from .conf import rtl_settings

try:  # pragma: no cover - exercised by both branches in CI
    from babel import Locale, UnknownLocaleError
    from babel import dates as babel_dates
    from babel import numbers as babel_numbers

    HAS_BABEL = True
except ImportError:  # pragma: no cover
    # Babel is optional.  The names stay importable so the rest of the module
    # can refer to them; `_use_babel()` keeps them from being used.  A type
    # checker sees the real Babel types above, hence the ignores on the
    # stand-ins.
    Locale = None  # type: ignore[assignment,misc]
    UnknownLocaleError = Exception  # type: ignore[assignment,misc]
    babel_dates = babel_numbers = None  # type: ignore[assignment]
    HAS_BABEL = False


#: Digits of every CLDR numbering system we support.
DIGITS: dict[str, str] = {
    "latn": "0123456789",
    "arab": "٠١٢٣٤٥٦٧٨٩",
    "arabext": "۰۱۲۳۴۵۶۷۸۹",
}

NUMBERING_SYSTEMS = tuple(DIGITS)

#: Used when Babel is unavailable.  Values match CLDR 46.
_FALLBACK_NUMBERING: dict[str, str] = {
    "ar": "latn",
    "ar_EG": "arab",
    "ar_SD": "arab",
    "ar_YE": "arab",
    "ar_SY": "arab",
    "ar_IQ": "arab",
    "ar_SA": "arab",
    "ar_JO": "arab",
    "ar_LB": "arab",
    "ar_PS": "arab",
    "ar_QA": "arab",
    "ar_KW": "arab",
    "ar_BH": "arab",
    "ar_OM": "arab",
    "ar_AE": "arab",
    "fa": "arabext",
    "ps": "arabext",
    "ur_IN": "arabext",
    "ckb": "arab",
    "dv": "arab",
}

# Reverse lookup: any supported digit -> its value.
_DIGIT_VALUES: dict[str, int] = {
    digit: value
    for digits in DIGITS.values()
    for value, digit in enumerate(digits)
}

_DJANGO_DATE_FORMATS = {
    "short": "SHORT_DATE_FORMAT",
    "medium": "DATE_FORMAT",
    "long": "DATE_FORMAT",
    "full": "DATE_FORMAT",
}
_DJANGO_DATETIME_FORMATS = {
    "short": "SHORT_DATETIME_FORMAT",
    "medium": "DATETIME_FORMAT",
    "long": "DATETIME_FORMAT",
    "full": "DATETIME_FORMAT",
}


def _active(language: str | None) -> contextlib.AbstractContextManager[None]:
    """Make Django's own l10n honour an explicit ``language`` argument.

    ``django.utils.formats`` always reads the *active* language, so without
    this the ``language=`` argument would be silently ignored whenever Babel is
    not in play.
    """
    if language is None:
        return contextlib.nullcontext()
    return translation.override(language)


def _use_babel() -> bool:
    return HAS_BABEL and bool(rtl_settings.USE_BABEL)


def _babel_locale(language: str | None) -> Locale | None:
    if not _use_babel():
        return None
    code = to_locale(language or get_language() or "en")
    try:
        return Locale.parse(code)
    except (UnknownLocaleError, ValueError, TypeError):
        try:
            return Locale.parse(code.split("_", 1)[0])
        except (UnknownLocaleError, ValueError, TypeError):
            return None


def numbering_system(language: str | None = None) -> str:
    """CLDR numbering system key for ``language``: ``latn``, ``arab`` or ``arabext``.

    ``RTL_ADMIN["NUMERALS"]`` short-circuits this: set it to ``"arab"`` to
    force Arabic-Indic digits regardless of what CLDR says about the locale.
    """
    configured = rtl_settings.NUMERALS
    if configured != "auto":
        return configured
    locale = _babel_locale(language)
    if locale is not None:
        system: str | None = getattr(locale, "default_numbering_system", None)
        if system in DIGITS:
            return system
        if system:
            return "latn"
    code = to_locale(language or get_language() or "en")
    if code in _FALLBACK_NUMBERING:
        return _FALLBACK_NUMBERING[code]
    return _FALLBACK_NUMBERING.get(code.split("_", 1)[0], "latn")


def transliterate_digits(text: str, to: str = "latn") -> str:
    """Rewrite every digit in ``text`` using the ``to`` numbering system."""
    if not text:
        return text
    if to not in DIGITS:
        raise ValueError(
            f"Unknown numbering system {to!r}; expected one of "
            f"{', '.join(NUMBERING_SYSTEMS)}."
        )
    target = DIGITS[to]
    return "".join(
        target[_DIGIT_VALUES[char]] if char in _DIGIT_VALUES else char
        for char in text
    )


def _localize_digits(text: str, language: str | None) -> str:
    return transliterate_digits(text, numbering_system(language))


def _localtime(value: Any) -> Any:
    if (
        settings.USE_TZ
        and isinstance(value, datetime.datetime)
        and timezone.is_aware(value)
    ):
        return timezone.localtime(value)
    return value


def format_number(
    value: Any,
    *,
    language: str | None = None,
    decimal_pos: int | None = None,
    grouping: bool = True,
) -> str:
    """Format a number for the active (or given) locale.

    Uses the locale's own group/decimal separators and numbering system, so
    ``1234567.891`` renders as ``1,234,567.891`` for ``en`` and
    ``١٬٢٣٤٬٥٦٧٫٨٩١`` for ``ar-eg``.
    """
    if value is None or value == "":
        return ""
    locale = _babel_locale(language)
    if locale is not None:
        pattern = None
        if decimal_pos is not None:
            pattern = "#,##0." + ("0" * decimal_pos) if decimal_pos else "#,##0"
        try:
            text = babel_numbers.format_decimal(
                value,
                format=pattern,
                locale=locale,
                group_separator=grouping,
                numbering_system="default",
            )
        except Exception:  # pragma: no cover - defensive
            text = None
        if text is not None:
            return _localize_digits(text, language)
    with _active(language):
        text = formats.number_format(
            value, decimal_pos=decimal_pos, force_grouping=grouping, use_l10n=True
        )
    return _localize_digits(str(text), language)


def format_currency(
    value: Any,
    currency: str | None = None,
    *,
    language: str | None = None,
) -> str:
    """Format ``value`` as money, using the locale's currency pattern."""
    if value is None or value == "":
        return ""
    currency = currency or rtl_settings.CURRENCY
    locale = _babel_locale(language)
    if locale is not None:
        try:
            text = babel_numbers.format_currency(
                value, currency, locale=locale, numbering_system="default"
            )
        except Exception:  # pragma: no cover - defensive
            text = None
        if text is not None:
            return _localize_digits(text, language)
    number = format_number(value, language=language, decimal_pos=2)
    return f"{number} {currency}"


def format_percent(value: Any, *, language: str | None = None) -> str:
    """Format a 0..1 ratio as a locale-aware percentage."""
    if value is None or value == "":
        return ""
    locale = _babel_locale(language)
    if locale is not None:
        try:
            return _localize_digits(
                babel_numbers.format_percent(
                    value, locale=locale, numbering_system="default"
                ),
                language,
            )
        except Exception:  # pragma: no cover - defensive
            pass
    percentage = (decimal.Decimal(str(value)) * 100).quantize(
        decimal.Decimal("1"), rounding=decimal.ROUND_HALF_UP
    )
    return f"{format_number(percentage, language=language, decimal_pos=0)}%"


def format_date(
    value: datetime.date | None,
    fmt: str = "medium",
    *,
    language: str | None = None,
) -> str:
    """Locale-aware date, with the locale's own digits."""
    if value is None:
        return ""
    locale = _babel_locale(language)
    if locale is not None:
        try:
            return _localize_digits(
                babel_dates.format_date(value, format=fmt, locale=locale), language
            )
        except Exception:  # pragma: no cover - defensive
            pass
    django_format = _DJANGO_DATE_FORMATS.get(fmt, fmt)
    with _active(language):
        text = formats.date_format(value, django_format, use_l10n=True)
    return _localize_digits(text, language)


def _format_datetime(
    value: datetime.datetime | None,
    fmt: str = "medium",
    *,
    language: str | None = None,
) -> str:
    if value is None:
        return ""
    locale = _babel_locale(language)
    if locale is not None:
        try:
            return _localize_digits(
                babel_dates.format_datetime(value, format=fmt, locale=locale),
                language,
            )
        except Exception:  # pragma: no cover - defensive
            pass
    django_format = _DJANGO_DATETIME_FORMATS.get(fmt, fmt)
    with _active(language):
        text = formats.date_format(value, django_format, use_l10n=True)
    return _localize_digits(text, language)


def format_datetime(
    value: datetime.datetime | None,
    fmt: str = "medium",
    *,
    language: str | None = None,
) -> str:
    """Locale-aware date and time, with the locale's own digits.

    When ``USE_TZ`` is enabled, aware datetimes are converted to the current
    time zone with ``django.utils.timezone.localtime()``; naive values are left
    untouched.
    """
    return _format_datetime(_localtime(value), fmt, language=language)


def _format_time(
    value: datetime.time | datetime.datetime | None,
    fmt: str = "medium",
    *,
    language: str | None = None,
) -> str:
    if value is None:
        return ""
    locale = _babel_locale(language)
    if locale is not None:
        try:
            return _localize_digits(
                babel_dates.format_time(value, format=fmt, locale=locale), language
            )
        except Exception:  # pragma: no cover - defensive
            pass
    with _active(language):
        text = formats.time_format(value, use_l10n=True)
    return _localize_digits(text, language)


def format_time(
    value: datetime.time | datetime.datetime | None,
    fmt: str = "medium",
    *,
    language: str | None = None,
) -> str:
    """Locale-aware time of day, with the locale's own digits.

    When ``USE_TZ`` is enabled, aware datetimes are converted to the current
    time zone with ``django.utils.timezone.localtime()``; naive values are left
    untouched.
    """
    return _format_time(_localtime(value), fmt, language=language)
