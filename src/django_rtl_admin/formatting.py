"""Locale-aware number, date and currency formatting.

Arabic locales do not all agree on how to write a number.  ``ar-EG`` uses
Arabic-Indic digits (``١٢٣``) with U+066C as the group separator and U+066B as
the decimal separator; ``ar-MA`` and plain ``ar`` use Latin digits with the
usual comma and full stop.  Django's ``USE_THOUSAND_SEPARATOR``/``L10N``
machinery has no concept of a numbering system at all, so an Arabic admin ends
up showing Latin digits everywhere no matter what the locale says.

These helpers use `Babel <https://babel.pocoo.org/>`_ when it is installed
(``pip install django-rtl-admin[babel]``). Without Babel, numbers use built-in
CLDR tables for digits, separators and grouping. Dates and times use Django's
locale formats, supplemented with CLDR patterns where locale data is missing.
"""

from __future__ import annotations

import contextlib
import datetime
import decimal
import re
import unicodedata
from collections.abc import Callable
from typing import Any

from django.conf import settings
from django.utils import dateformat, formats, timesince, timezone, translation
from django.utils.html import avoid_wrapping
from django.utils.text import slugify
from django.utils.translation import get_language, gettext, npgettext, pgettext, to_locale

from .bidi import BIDI_CONTROL_CHARS
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

_NUMERIC_INPUT_TABLE = str.maketrans(
    DIGITS["arab"] + DIGITS["arabext"] + "\u2212",
    DIGITS["latn"] * 2 + "-",
    "\u066c" + "".join(BIDI_CONTROL_CHARS),
)

_ARABIC_DIACRITICS_AND_TATWEEL = (
    "\u0640" + "".join(chr(cp) for cp in range(0x064B, 0x0660)) + "\u0670"
)
_ARABIC_DIACRITICS_RE = "[\u0640\u064b-\u065f\u0670]*"
_ARABIC_SEARCH_DROPPED = frozenset(_ARABIC_DIACRITICS_AND_TATWEEL) | BIDI_CONTROL_CHARS
_ARABIC_LETTER_GROUPS: tuple[str, ...] = (
    "\u0622\u0623\u0625\u0627\u0671",  # آ أ إ ا ٱ
    "\u0629\u0647",  # ة ه
    "\u0626\u0649\u064a\u06cc",  # ئ ى ي ی
    "\u0643\u06a9",  # ك ک
    "\u0624\u0648",  # ؤ و
)
_ARABIC_LETTER_CLASS: dict[str, str] = {
    char: f"[{group}]" for group in _ARABIC_LETTER_GROUPS for char in group
}
_DIGIT_SEARCH_CLASS: dict[str, str] = {
    char: f"[{latn}{arab}{ext}]"
    for latn, arab, ext in zip(DIGITS["latn"], DIGITS["arab"], DIGITS["arabext"], strict=True)
    for char in (latn, arab, ext)
}
_ARABIC_DIGITS = frozenset(DIGITS["arab"] + DIGITS["arabext"])

# Stable, letter-by-letter romanisation, not a phonetic transcription. Keep
# the table in sync with static/django_rtl_admin/js/slug.js and the API docs.
_ARABIC_ROMANIZATION = str.maketrans(
    {
        char: latin
        for letters, latin in (
            ("اأإآٱءعى", "a"),
            ("ب", "b"),
            ("تط", "t"),
            ("ث", "th"),
            ("ج", "j"),
            ("حةهہۀە", "h"),
            ("خ", "kh"),
            ("دض", "d"),
            ("ذ", "dh"),
            ("ر", "r"),
            ("زظ", "z"),
            ("سص", "s"),
            ("ش", "sh"),
            ("غ", "gh"),
            ("ف", "f"),
            ("ق", "q"),
            ("كک", "k"),
            ("ل", "l"),
            ("م", "m"),
            ("ن", "n"),
            ("وؤ", "w"),
            ("يیئ", "y"),
            ("پ", "p"),
            ("چ", "ch"),
            ("ژ", "zh"),
            ("گ", "g"),
        )
        for char in letters
    }
)
_SLUG_CLEANUP = str.maketrans(
    DIGITS["arab"] + DIGITS["arabext"], DIGITS["latn"] * 2, "".join(_ARABIC_SEARCH_DROPPED)
)
_ARABIC_SLUG_INPUT = re.compile(
    r"[\u0600-\u06ff\u0750-\u077f\u0870-\u08ff\ufb50-\ufdff\ufe70-\ufefc"
    r"\U00010ec0-\U00010eff\U0001ee00-\U0001eeff]"
)

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

#: CLDR 47 Gregorian long date, short date and short time, in Django syntax.
#: Source: unicode-org/cldr, release-47, common/main/{ur,ug}.xml. Django
#: doesn't ship Urdu formats; its Uyghur format module was added in 5.0.
_FALLBACK_DATE_TIME_FORMATS = {
    "ur": {"DATE_FORMAT": "j F، Y", "SHORT_DATE_FORMAT": "j/n/y", "TIME_FORMAT": "g:i A"},
    "ug": {"DATE_FORMAT": "j-F، Y", "SHORT_DATE_FORMAT": "Y-m-d", "TIME_FORMAT": "H:i"},
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

#: The no-Babel duration wording, per unit: (plain, past, future).  Django's
#: ``timesince`` strings cover every unit except seconds, and in Arabic they
#: put a number in front of the singular and the dual (``٢ دقيقتين``), so the
#: package's catalogs carry their own forms under the ``duration`` context.
#: A form the active catalog does not translate falls back to Django's unit
#: string and the generic ``"%(delta)s ago"`` / ``"%(delta)s from now"``.
_DURATION_FORMS: dict[str, tuple[Callable[[int], str], ...]] = {
    "year": (
        lambda n: npgettext("duration", "%(num)s year", "%(num)s years", n),
        lambda n: npgettext("duration", "%(num)s year ago", "%(num)s years ago", n),
        lambda n: npgettext("duration", "in %(num)s year", "in %(num)s years", n),
    ),
    "month": (
        lambda n: npgettext("duration", "%(num)s month", "%(num)s months", n),
        lambda n: npgettext("duration", "%(num)s month ago", "%(num)s months ago", n),
        lambda n: npgettext("duration", "in %(num)s month", "in %(num)s months", n),
    ),
    "week": (
        lambda n: npgettext("duration", "%(num)s week", "%(num)s weeks", n),
        lambda n: npgettext("duration", "%(num)s week ago", "%(num)s weeks ago", n),
        lambda n: npgettext("duration", "in %(num)s week", "in %(num)s weeks", n),
    ),
    "day": (
        lambda n: npgettext("duration", "%(num)s day", "%(num)s days", n),
        lambda n: npgettext("duration", "%(num)s day ago", "%(num)s days ago", n),
        lambda n: npgettext("duration", "in %(num)s day", "in %(num)s days", n),
    ),
    "hour": (
        lambda n: npgettext("duration", "%(num)s hour", "%(num)s hours", n),
        lambda n: npgettext("duration", "%(num)s hour ago", "%(num)s hours ago", n),
        lambda n: npgettext("duration", "in %(num)s hour", "in %(num)s hours", n),
    ),
    "minute": (
        lambda n: npgettext("duration", "%(num)s minute", "%(num)s minutes", n),
        lambda n: npgettext("duration", "%(num)s minute ago", "%(num)s minutes ago", n),
        lambda n: npgettext("duration", "in %(num)s minute", "in %(num)s minutes", n),
    ),
    "second": (
        lambda n: npgettext("duration", "%(num)s second", "%(num)s seconds", n),
        lambda n: npgettext("duration", "%(num)s second ago", "%(num)s seconds ago", n),
        lambda n: npgettext("duration", "in %(num)s second", "in %(num)s seconds", n),
    ),
}

#: File size units.  The package translates them under its own ``file size``
#: context so that its catalogs never override Django's ``"%s KB"`` strings
#: (and with them Django's own ``filesizeformat``); a language the package does
#: not ship falls back to Django's translation.
_FILESIZE_UNITS: tuple[tuple[Callable[[], str], str], ...] = (
    (lambda: pgettext("file size", "%s KB"), "%s KB"),
    (lambda: pgettext("file size", "%s MB"), "%s MB"),
    (lambda: pgettext("file size", "%s GB"), "%s GB"),
    (lambda: pgettext("file size", "%s TB"), "%s TB"),
    (lambda: pgettext("file size", "%s PB"), "%s PB"),
)

#: CLDR minus signs for the numbering systems, used when Babel is unavailable:
#: ARABIC LETTER MARK + hyphen-minus for ``arab``, LEFT-TO-RIGHT MARK + U+2212
#: MINUS SIGN for ``arabext`` (``fa``).
_FALLBACK_MINUS_SIGNS = {"arab": "\u061c-", "arabext": "\u200e\u2212"}


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


def normalize_numeric_input(value: Any, *, decimal_separator: str = ".") -> Any:
    """Normalize localized numeric text without parsing or validating it.

    Convert Arabic-Indic and extended Arabic-Indic digits, the Arabic decimal
    separator and the Unicode minus sign. Drop bidi controls, Arabic thousands
    separators and outer whitespace. Nonbreaking, narrow nonbreaking and thin
    spaces are removed inside the text only when flanked by digits. Leave
    other punctuation (including commas and periods) and non-string values alone.
    """
    if not isinstance(value, str):
        return value
    text = value.translate(_NUMERIC_INPUT_TABLE).strip()
    text = re.sub(r"(?<=\d)[\u00a0\u202f\u2009](?=\d)", "", text)
    return text.replace("\u066b", decimal_separator)


def _is_arabic_letter(char: str) -> bool:
    code = ord(char)
    if not (
        0x0600 <= code <= 0x06FF
        or 0x0750 <= code <= 0x077F
        or 0x0870 <= code <= 0x08FF
        or 0xFB50 <= code <= 0xFDFF
        or 0xFE70 <= code <= 0xFEFF
        or 0x10EC0 <= code <= 0x10EFF
        or 0x1EE00 <= code <= 0x1EEFF
    ):
        return False
    return char != "\u0640" and unicodedata.category(char).startswith("L")


def _has_arabic_search_chars(term: str) -> bool:
    return any(char in _ARABIC_DIGITS or _is_arabic_letter(char) for char in term)


def _has_foldable_search_chars(term: str) -> bool:
    return any(char in _DIGIT_SEARCH_CLASS or _is_arabic_letter(char) for char in term)


def arabic_search_regex(term: str) -> str:
    """Build a portable regex matching equivalent Arabic forms and digits.

    Strip harakat (U+064B--U+065F, U+0670), tatweel (U+0640) and Unicode
    ``Bidi_Control`` characters from ``term``.  Fold equivalent Arabic letters
    and digits (ASCII, Arabic-Indic and Persian) into bracket character
    classes, allow optional harakat or tatweel after every Arabic letter, and
    place punctuation and symbols in single-character classes so the pattern
    runs unchanged on SQLite, PostgreSQL and MySQL 8.
    """
    parts: list[str] = []
    for char in term:
        if char in _ARABIC_SEARCH_DROPPED:
            continue
        letter_class = _ARABIC_LETTER_CLASS.get(char)
        if letter_class is not None:
            parts.append(letter_class + _ARABIC_DIACRITICS_RE)
        elif _is_arabic_letter(char):
            parts.append(char + _ARABIC_DIACRITICS_RE)
        elif char in _DIGIT_SEARCH_CLASS:
            parts.append(_DIGIT_SEARCH_CLASS[char])
        elif unicodedata.category(char)[0] in ("P", "S"):
            parts.append(f"[\\{char}]" if char in r"[\^:]" else f"[{char}]")
        else:
            parts.append(char)
    return "".join(parts)


def arabic_slugify(
    value: Any, *, allow_unicode: bool = False, max_length: int | None = None
) -> str:
    """Make a slug from Arabic or Persian text, independent of the UI locale.

    Remove harakat, tatweel and bidi controls, and convert both Arabic digit
    sets to ASCII. With ``allow_unicode=True`` the remaining text is passed to
    Django's Unicode slugifier. Otherwise Arabic and Persian letters are
    romanised with a fixed letter-by-letter table before Django slugifies them.
    Arabic input that would otherwise produce an empty ASCII slug yields
    ``"arabic"``.

    When shortening, keep complete hyphen-separated segments if possible;
    hard-cut the first segment if it cannot fit. A nonpositive limit yields
    the empty string. ``None`` and empty strings always return an empty slug.
    """
    if value is None or (isinstance(value, str) and not value):
        return ""
    text = str(value)
    if allow_unicode:
        slug = slugify(text.translate(_SLUG_CLEANUP), allow_unicode=True)
    else:
        cleaned = unicodedata.normalize("NFKC", text).translate(_SLUG_CLEANUP)
        slug = slugify(cleaned.translate(_ARABIC_ROMANIZATION))
        if not slug and _ARABIC_SLUG_INPUT.search(text):
            slug = "arabic"
    if max_length is None or len(slug) <= max_length:
        return slug
    if max_length <= 0:
        return ""
    boundary = slug.rfind("-", 0, max_length + 1)
    return slug[: max_length if boundary == -1 else boundary].rstrip("-_")


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


def _duration_form(form: Callable[[int], str], amount: int) -> str | None:
    """Render a package duration form, or ``None`` if the catalog lacks it."""
    text = form(amount)
    with translation.override(None):
        untranslated = form(amount)
    if text == untranslated:
        return None
    return text % {"num": amount}


def _fallback_timedelta(
    value: datetime.timedelta | decimal.Decimal,
    granularity: str,
    threshold: float,
    add_direction: bool,
    language: str | None,
) -> str:
    """Format a duration from the gettext catalogs (package, then Django)."""
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
    plain, past, future = _DURATION_FORMS[unit]
    with _active(language):
        text = None
        if add_direction:
            text = _duration_form(past if negative else future, amount)
        if text is None:
            text = _duration_form(plain, amount)
            if text is None:
                if unit == "second":
                    # Django has no seconds string; use the English wording.
                    text = plain(amount) % {"num": amount}
                else:
                    # ngettext_lazy resolves against the active language, so
                    # this must stay inside the override.
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


def _minus_sign(language: str | None) -> str:
    """The locale's minus sign: Babel's number symbol, else the CLDR default."""
    system = numbering_system(language)
    locale = _babel_locale(language)
    if locale is not None:
        try:
            try:
                sign: str = babel_numbers.get_minus_sign_symbol(locale, numbering_system=system)
            except TypeError:  # pragma: no cover - Babel < 2.14 has no numbering_system
                sign = babel_numbers.get_minus_sign_symbol(locale)
        except Exception:  # pragma: no cover - defensive
            pass
        else:
            return sign
    return _FALLBACK_MINUS_SIGNS.get(system, "-")


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
        package_template, django_msgid = _FILESIZE_UNITS[exponent - 1]
        with _active(language):
            template = package_template()
            if template == django_msgid:
                template = gettext(django_msgid)
        text = template % formatted
    if negative:
        text = _minus_sign(language) + text
    return _localize_digits(avoid_wrapping(text), language)


def _django_pattern(name: str) -> str:
    """Resolve a display pattern inside the caller's active language override."""
    lang = get_language()
    # get_format() alone can't distinguish a locale definition from a global
    # default. Django orders these modules project-first, then region/base.
    modules = formats.get_format_modules(lang)
    for module in modules:
        pattern = getattr(module, name, None)
        if pattern is not None:
            return str(pattern)

    base = to_locale(lang or "en").split("_", 1)[0]
    defaults = _FALLBACK_DATE_TIME_FORMATS.get(base, {})
    if name in defaults:
        return defaults[name]
    if (modules or defaults) and name in ("DATETIME_FORMAT", "SHORT_DATETIME_FORMAT"):
        date = "SHORT_DATE_FORMAT" if name == "SHORT_DATETIME_FORMAT" else "DATE_FORMAT"
        return f"{_django_pattern(date)} {_django_pattern('TIME_FORMAT')}"

    # Custom patterns and locales without any format data still use Django.
    return str(formats.get_format(name, use_l10n=True))


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
        text = dateformat.format(value, _django_pattern(django_format or "DATE_FORMAT"))
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
        text = dateformat.format(value, _django_pattern(django_format or "DATE_FORMAT"))
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
    django_format = "TIME_FORMAT" if fmt in _DJANGO_DATE_FORMATS else fmt
    with _active(language):
        text = dateformat.time_format(value, _django_pattern(django_format or "TIME_FORMAT"))
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
