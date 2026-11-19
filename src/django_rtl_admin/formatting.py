"""Locale-aware number, date and currency formatting.

Arabic locales do not all agree on how to write a number.  ``ar-EG`` uses
Arabic-Indic digits (``١٢٣``) with U+066C as the group separator and U+066B as
the decimal separator; ``ar-MA`` and plain ``ar`` use Latin digits with the
usual comma and full stop.  Django's ``USE_THOUSAND_SEPARATOR``/``L10N``
machinery has no concept of a numbering system at all, so an Arabic admin ends
up showing Latin digits everywhere no matter what the locale says.

These helpers use `Babel <https://babel.pocoo.org/>`_ when it is installed --
``pip install django-rtl-admin[babel]`` -- and fall back to a small built-in
CLDR table (numbering system, separators and grouping per locale) when it is
not, deferring to Django's own ``django.utils.formats`` only for locales the
table does not cover.  Nothing here raises if Babel is missing.
"""

from __future__ import annotations

import contextlib
import datetime
import decimal
from typing import Any

from django.conf import settings
from django.utils import formats, timesince, timezone, translation
from django.utils.html import avoid_wrapping
from django.utils.translation import get_language, gettext, ngettext, to_locale

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

#: Used when Babel is unavailable.  Values match CLDR 46.  Locales absent
#: from the table inherit from their base language; anything without an entry
#: anywhere gets Latin digits.  Note ``ar-AE`` and ``dv``: both use Latin
#: digits even though their neighbours do not.
_FALLBACK_NUMBERING: dict[str, str] = {
    "ar": "latn",
    "ar_AE": "latn",
    "ar_BH": "arab",
    "ar_DJ": "arab",
    "ar_EG": "arab",
    "ar_ER": "arab",
    "ar_IL": "arab",
    "ar_IQ": "arab",
    "ar_JO": "arab",
    "ar_KM": "arab",
    "ar_KW": "arab",
    "ar_LB": "arab",
    "ar_MR": "arab",
    "ar_OM": "arab",
    "ar_PS": "arab",
    "ar_QA": "arab",
    "ar_SA": "arab",
    "ar_SD": "arab",
    "ar_SO": "arab",
    "ar_SS": "arab",
    "ar_SY": "arab",
    "ar_TD": "arab",
    "ar_YE": "arab",
    "ckb": "arab",
    "dv": "latn",
    "fa": "arabext",
    "ps": "arabext",
    "ur_IN": "arabext",
}

#: (group separator, decimal separator) per locale, used when Babel is
#: unavailable.  Keys are Django locale codes (``to_locale()`` output);
#: unlisted locales inherit from their base language.  Values match the
#: symbols CLDR assigns to each locale's *default* numbering system.
_LATIN_SEPARATORS = (",", ".")
_ARABIC_SEPARATORS = ("\u066c", "\u066b")  # ARABIC THOUSANDS / DECIMAL SEPARATOR
_EUROPEAN_SEPARATORS = (".", ",")
_NBSP_SEPARATORS = ("\xa0", ",")

_FALLBACK_SEPARATORS: dict[str, tuple[str, str]] = {
    code: separators
    for separators, codes in (
        (_LATIN_SEPARATORS, ("ar", "dv", "en", "he", "ur")),
        (
            _ARABIC_SEPARATORS,
            (
                "ar_BH",
                "ar_DJ",
                "ar_EG",
                "ar_ER",
                "ar_IL",
                "ar_IQ",
                "ar_JO",
                "ar_KM",
                "ar_KW",
                "ar_LB",
                "ar_MR",
                "ar_OM",
                "ar_PS",
                "ar_QA",
                "ar_SA",
                "ar_SD",
                "ar_SO",
                "ar_SS",
                "ar_SY",
                "ar_TD",
                "ar_YE",
                "ckb",
                "fa",
                "ps",
                "ur_IN",
            ),
        ),
        (_EUROPEAN_SEPARATORS, ("ar_DZ", "ar_LY", "ar_MA", "ar_TN")),
        (_NBSP_SEPARATORS, ("kk",)),
    )
    for code in codes
}

#: Digit group sizes, right to left, for locales that do not group by three.
#: The last size repeats (``dv``: ``12,34,567``).  Only applies when the
#: caller left ``decimal_pos`` alone; an explicit position always groups by
#: three, matching Babel's ``#,##0`` patterns.
_FALLBACK_GROUP_SIZES: dict[str, tuple[int, ...]] = {
    "dv": (3, 2),
    "en_IN": (3, 2),
}

# Reverse lookup: any supported digit -> its value.
_DIGIT_VALUES: dict[str, int] = {
    digit: value for digits in DIGITS.values() for value, digit in enumerate(digits)
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

#: Babel's duration units and their length in seconds.  Kept in the same order
#: so the no-Babel fallback picks the same unit as Babel.
_DURATION_UNITS: tuple[tuple[str, int], ...] = (
    ("year", 31_536_000),
    ("month", 2_592_000),
    ("week", 604_800),
    ("day", 86_400),
    ("hour", 3_600),
    ("minute", 60),
    ("second", 1),
)

#: Django's timesince strings cover every unit except seconds; the fallback
#: gets the missing second forms and direction wording from the package's own
#: gettext catalogs.
_FILESIZE_UNITS = ("KB", "MB", "GB", "TB", "PB")
_FILESIZE_UNIT_TEMPLATES = {unit: f"%s {unit}" for unit in _FILESIZE_UNITS}


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
            f"Unknown numbering system {to!r}; expected one of {', '.join(NUMBERING_SYSTEMS)}."
        )
    target = DIGITS[to]
    return "".join(target[_DIGIT_VALUES[char]] if char in _DIGIT_VALUES else char for char in text)


def _localize_digits(text: str, language: str | None) -> str:
    return transliterate_digits(text, numbering_system(language))


def _localtime(value: Any) -> Any:
    if settings.USE_TZ and isinstance(value, datetime.datetime) and timezone.is_aware(value):
        return timezone.localtime(value)
    return value


def _as_decimal(value: Any) -> decimal.Decimal:
    try:
        number = value if isinstance(value, decimal.Decimal) else decimal.Decimal(str(value))
    except (decimal.InvalidOperation, TypeError, ValueError):
        raise ValueError(f"Value must be numeric, got {value!r}") from None
    if not number.is_finite():
        raise ValueError(f"Value must be finite, got {value!r}")
    return number


def _fallback_separators(code: str) -> tuple[str, str] | None:
    """CLDR separators for a Django locale code, or ``None`` if unknown."""
    if code in _FALLBACK_SEPARATORS:
        return _FALLBACK_SEPARATORS[code]
    return _FALLBACK_SEPARATORS.get(code.split("_", 1)[0])


def _fallback_group_sizes(code: str) -> tuple[int, ...]:
    if code in _FALLBACK_GROUP_SIZES:
        return _FALLBACK_GROUP_SIZES[code]
    return _FALLBACK_GROUP_SIZES.get(code.split("_", 1)[0], (3,))


def _quantize(number: decimal.Decimal, decimal_pos: int | None) -> decimal.Decimal:
    """Round like Babel's ``#,##0.###`` (default) or ``#,##0.00`` patterns.

    ``decimal_pos=None`` keeps at most three fraction digits and strips
    trailing zeros; an explicit position keeps exactly that many.  Both round
    half-to-even.
    """
    keep = 3 if decimal_pos is None else decimal_pos
    exponent = decimal.Decimal(1).scaleb(-keep)
    width = len(format(number, "f")) + keep + 1
    with decimal.localcontext() as context:
        # quantize() raises InvalidOperation when the result does not fit the
        # context precision; huge inputs (10**20 and up) need a wider one.
        context.prec = max(context.prec, width)
        quantized = number.quantize(exponent, rounding=decimal.ROUND_HALF_EVEN)
        if decimal_pos is None:
            # normalize() is a context operation too: strip trailing zeros
            # under the widened precision so Decimals with more significant
            # digits than the default context keep every digit.
            quantized = quantized.normalize()
    return quantized


def _group_digits(digits: str, sizes: tuple[int, ...], separator: str) -> str:
    """Insert ``separator`` into an integer digit string, right to left.

    ``sizes`` gives the group widths right to left; the last one repeats
    (``(3, 2)`` renders ``1234567`` as ``12,34,567``).
    """
    if not separator or len(digits) <= sizes[0]:
        return digits
    chunks: list[str] = []
    remaining = digits
    index = 0
    while len(remaining) > (size := sizes[min(index, len(sizes) - 1)]):
        chunks.append(remaining[-size:])
        remaining = remaining[:-size]
        index += 1
    chunks.append(remaining)
    return separator.join(reversed(chunks))


def _render_number(
    number: decimal.Decimal,
    code: str,
    separators: tuple[str, str],
    language: str | None,
    *,
    grouping: bool,
    decimal_pos: int | None,
) -> str:
    """Format ``number`` from the fallback CLDR tables, Babel-style."""
    group_separator, decimal_separator = separators
    sizes = (3,) if decimal_pos is not None else _fallback_group_sizes(code)
    text = format(_quantize(number, decimal_pos), "f")
    sign = "-" if text.startswith("-") else ""
    digits, _, fraction = text[len(sign) :].partition(".")
    rendered = _group_digits(digits, sizes, group_separator if grouping else "")
    if fraction:
        rendered += decimal_separator + fraction
    return _localize_digits(sign + rendered, language)


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
    code = to_locale(language or get_language() or "en")
    separators = _fallback_separators(code)
    if separators is not None:
        try:
            number = _as_decimal(value)
        except ValueError:
            number = None  # Not numeric: let Django's formatter deal with it.
        if number is not None:
            return _render_number(
                number,
                code,
                separators,
                language,
                grouping=grouping,
                decimal_pos=decimal_pos,
            )
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
    try:
        number = _as_decimal(value)
    except ValueError:
        raise ValueError(f"Currency value must be numeric, got {value!r}") from None
    currency = currency or rtl_settings.CURRENCY
    if not isinstance(currency, str):
        raise ValueError(f"Currency code must be three ASCII letters, got {currency!r}")
    currency = currency.strip()
    if len(currency) != 3 or not currency.isascii() or not currency.isalpha():
        raise ValueError(f"Currency code must be three ASCII letters, got {currency!r}")
    currency = currency.upper()
    locale = _babel_locale(language)
    if locale is not None:
        try:
            text = babel_numbers.format_currency(
                number, currency, locale=locale, numbering_system="default"
            )
        except Exception:  # pragma: no cover - defensive
            text = None
        if text is not None:
            return _localize_digits(text, language)
    formatted = format_number(number, language=language, decimal_pos=2)
    return f"{formatted} {currency}"


def format_percent(value: Any, *, language: str | None = None) -> str:
    """Format a 0..1 ratio as a locale-aware percentage."""
    if value is None or value == "":
        return ""
    try:
        number = _as_decimal(value)
    except ValueError:
        raise ValueError(f"Percentage value must be numeric and finite, got {value!r}") from None
    locale = _babel_locale(language)
    if locale is not None:
        try:
            return _localize_digits(
                babel_numbers.format_percent(value, locale=locale, numbering_system="default"),
                language,
            )
        except Exception:  # pragma: no cover - defensive
            pass
    percentage = _quantize(number * 100, 0)
    return f"{format_number(percentage, language=language, decimal_pos=0)}%"


def _second_text(amount: int) -> str:
    """Spell a number of seconds from the package's gettext catalog."""
    return ngettext("%(num)s second", "%(num)s seconds", amount) % {"num": amount}


def _fallback_timedelta(
    value: datetime.timedelta | decimal.Decimal,
    granularity: str,
    threshold: float,
    add_direction: bool,
    language: str | None,
) -> str:
    """Format a duration with Django's translated unit strings."""
    seconds: decimal.Decimal
    if isinstance(value, datetime.timedelta):
        # Babel ignores microseconds and normalizes negative deltas this way.
        seconds = decimal.Decimal(value.days * 86_400 + value.seconds)
    else:
        seconds = value

    negative = seconds < 0
    magnitude = -seconds if negative else seconds
    threshold_decimal = decimal.Decimal(str(threshold))
    chosen: tuple[str, int] | None = None
    for unit, seconds_per_unit in _DURATION_UNITS:
        value_in_unit = magnitude / seconds_per_unit
        if value_in_unit >= threshold_decimal or unit == granularity:
            if unit == granularity and value_in_unit > 0:
                value_in_unit = max(decimal.Decimal(1), value_in_unit)
            chosen = (unit, round(value_in_unit))
            break
    if chosen is None:
        return ""

    unit, amount = chosen
    with _active(language):
        if unit == "second":
            text = _second_text(amount)
        else:
            # ngettext_lazy resolves against the active language, so this must
            # stay inside the override.
            text = str(timesince.TIME_STRINGS[unit] % {"num": amount})
        if add_direction:
            if negative:
                template = gettext("%(delta)s ago")
            else:
                template = gettext("%(delta)s from now")
            text = template % {"delta": text}
    return _localize_digits(text, language)


def format_timedelta(
    value: Any,
    *,
    granularity: str = "second",
    threshold: float = 0.85,
    add_direction: bool = False,
    format: str = "long",
    language: str | None = None,
) -> str:
    """Format a duration the way ``babel.dates.format_timedelta`` does.

    ``value`` is a :class:`datetime.timedelta` or a number of seconds.  Babel
    supplies CLDR unit patterns and direction wording when it is installed;
    otherwise Django's translated ``timesince`` unit strings are used.  The
    result always follows ``NUMERALS`` and an explicit ``language``.
    """
    if value is None or value == "":
        return ""
    if isinstance(value, datetime.timedelta):
        duration: Any = value
    else:
        try:
            duration = _as_decimal(value)
        except ValueError:
            raise ValueError(f"Timedelta value must be numeric, got {value!r}") from None

    locale = _babel_locale(language)
    if locale is not None:
        try:
            text = babel_dates.format_timedelta(
                duration,
                granularity=granularity,  # type: ignore[arg-type]
                threshold=threshold,
                add_direction=add_direction,
                format=format,  # type: ignore[arg-type]
                locale=locale,
            )
        except Exception:  # pragma: no cover - defensive
            pass
        else:
            return _localize_digits(text, language)
    return _fallback_timedelta(duration, granularity, threshold, add_direction, language)


def _filesize_bytes(number: decimal.Decimal, language: str | None) -> str:
    """Render a value below the first unit boundary through Django."""
    from django.template.defaultfilters import filesizeformat

    with _active(language):
        text = str(filesizeformat(int(number)))
    return _localize_digits(text, language)


def format_filesize(num_bytes: Any, *, binary: bool = False, language: str | None = None) -> str:
    """Format a byte count with locale-aware digits and unit spacing.

    ``binary=False`` (the default) uses powers of 1000; ``binary=True`` uses
    powers of 1024, matching Django's ``filesizeformat``.  Babel, when
    available, provides the locale's number separators and digits.
    """
    if num_bytes is None or num_bytes == "":
        return ""
    try:
        number = _as_decimal(num_bytes)
    except ValueError:
        raise ValueError(f"File size value must be numeric, got {num_bytes!r}") from None

    negative = number < 0
    magnitude = abs(number)
    base = 1024 if binary else 1000
    if magnitude < base:
        text = _filesize_bytes(magnitude, language)
    else:
        limit = base
        exponent = 1
        while magnitude >= limit * base and exponent < len(_FILESIZE_UNITS):
            limit *= base
            exponent += 1
        scaled = magnitude / limit
        formatted = format_number(scaled, language=language, decimal_pos=1)
        unit = _FILESIZE_UNITS[exponent - 1]
        with _active(language):
            template = gettext(_FILESIZE_UNIT_TEMPLATES[unit])
        text = template % formatted
    if negative:
        text = f"-{text}"
    return _localize_digits(avoid_wrapping(text), language)


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
