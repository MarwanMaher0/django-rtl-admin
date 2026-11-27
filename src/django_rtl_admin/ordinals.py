"""Arabic ordinal words and short locale ordinals.

Neither Python nor Django can write "the third floor" in Arabic: there is no
ordinal counterpart to ``django.contrib.humanize``'s ``ordinal`` for Arabic
words, so invoices, rankings, steps and floor numbers end up as bare digits or
as an English ``1st`` in the middle of an Arabic page.

``ordinal_words()`` spells an ordinal in Modern Standard Arabic (Fusha),
agreeing in gender and definiteness with the noun it follows, and
``ordinal_short()`` writes the compact form a locale uses next to digits.
``ordinal_display()`` turns an integer model field into a
``ModelAdmin.list_display`` column of ordinal words.

The words are unvocalized, as Arabic interfaces are, with two exceptions that
are written everywhere: the *tanwin* of the defective forms ``ثانٍ`` and
``حادٍ`` and of an accusative counted noun such as ``ألفًا``.  They are in the
nominative case (``العشرون``, not ``العشرين``), the form used for a heading, a
label or a table cell.
"""

from __future__ import annotations

import operator
import re
from typing import TYPE_CHECKING, Any, Literal, NamedTuple, Protocol, cast

from django.db.models.constants import LOOKUP_SEP
from django.utils.translation import get_language

from .conf import rtl_settings
from .formatting import numbering_system, transliterate_digits

if TYPE_CHECKING:
    from django.utils.functional import _StrOrPromise

#: Accepted spellings of the ``gender`` argument.
Gender = Literal["masculine", "feminine", "m", "f"]

#: Written before the digits of a short Arabic ordinal: the definite article
#: followed by a tatweel (U+0640), as in ``الذكرى الـ25``.
ARABIC_SHORT_ORDINAL_MARKER = "\u0627\u0644\u0640"

#: The largest value ``ordinal_words()`` spells out.
MAX_ORDINAL_WORDS = 999_999_999_999

_ARTICLE = "ال"

_GENDERS: dict[str, bool] = {"masculine": False, "m": False, "feminine": True, "f": True}

# 1 to 10, indexed by value.  Index 0 is unused.
_MASCULINE = ("", "أول", "ثاني", "ثالث", "رابع", "خامس", "سادس", "سابع", "ثامن", "تاسع", "عاشر")
_FEMININE = (
    "",
    "أولى",
    "ثانية",
    "ثالثة",
    "رابعة",
    "خامسة",
    "سادسة",
    "سابعة",
    "ثامنة",
    "تاسعة",
    "عاشرة",
)

# "First" inside a compound (11, 21, 31...) is a different word from 1 itself.
_COMPOUND_FIRST_MASCULINE = "حادي"
_COMPOUND_FIRST_FEMININE = "حادية"

# Defective masculine forms drop their final ya and take tanwin when they are
# indefinite, except as the first half of 11 to 19, which is invariable.
_DEFECTIVE_INDEFINITE = {"ثاني": "ثانٍ", "حادي": "حادٍ"}

# 20 to 90, indexed by the tens digit.  The tens have one form for both genders.
_TENS = ("", "", "عشرون", "ثلاثون", "أربعون", "خمسون", "ستون", "سبعون", "ثمانون", "تسعون")

# 100 to 900, indexed by the hundreds digit, and the form 200 takes in front
# of a counted noun (the dual loses its final nun: ``مئتا ألف``).
_HUNDREDS = (
    "",
    "مئة",
    "مئتان",
    "ثلاثمئة",
    "أربعمئة",
    "خمسمئة",
    "ستمئة",
    "سبعمئة",
    "ثمانمئة",
    "تسعمئة",
)
_HUNDREDS_CONSTRUCT = (*_HUNDREDS[:2], "مئتا", *_HUNDREDS[3:])

# Cardinals 3 to 10 as they count a masculine noun (thousand, million, billion).
_CARDINALS = ("", "", "", "ثلاثة", "أربعة", "خمسة", "ستة", "سبعة", "ثمانية", "تسعة", "عشرة")


class _Scale(NamedTuple):
    """A counted power of a thousand, in the forms the count selects."""

    value: int
    singular: str
    dual: str
    plural: str
    accusative: str


_SCALES = (
    _Scale(10**9, "مليار", "ملياران", "مليارات", "مليارًا"),
    _Scale(10**6, "مليون", "مليونان", "ملايين", "مليونًا"),
    _Scale(10**3, "ألف", "ألفان", "آلاف", "ألفًا"),
)

_INTEGER_TEXT = re.compile(r"[+-]?[0-9]+")

_ENGLISH_SUFFIXES = {1: "st", 2: "nd", 3: "rd"}


def _positive_int(value: Any) -> int:
    """Return ``value`` as an ``int`` of at least 1, or raise ``ValueError``."""
    if isinstance(value, bool):
        raise ValueError(f"An ordinal needs a positive integer, not the boolean {value!r}.")
    if isinstance(value, str):
        text = transliterate_digits(value.strip(), "latn")
        if not _INTEGER_TEXT.fullmatch(text):
            raise ValueError(
                f"An ordinal needs a positive integer, not the non-integer string {value!r}."
            )
        number = int(text)
    else:
        try:
            number = operator.index(value)
        except TypeError:
            raise ValueError(
                f"An ordinal needs a positive integer, not the {type(value).__name__} {value!r}."
            ) from None
    if number < 1:
        raise ValueError(f"An ordinal needs a positive integer, starting at 1; got {value!r}.")
    return number


def _is_feminine(gender: object) -> bool:
    key = gender.strip().lower() if isinstance(gender, str) else None
    if key not in _GENDERS:
        raise ValueError(
            f"gender must be 'masculine' or 'feminine' (or the short 'm' or 'f'), got {gender!r}."
        )
    return _GENDERS[key]


def _unit(
    unit: int, *, feminine: bool, definite: bool, compound: bool = False, teen: bool = False
) -> str:
    """The ordinal of 1 to 10, or the units half of a compound."""
    if feminine:
        word = _COMPOUND_FIRST_FEMININE if compound and unit == 1 else _FEMININE[unit]
    else:
        word = _COMPOUND_FIRST_MASCULINE if compound and unit == 1 else _MASCULINE[unit]
        if not definite and not teen:
            word = _DEFECTIVE_INDEFINITE.get(word, word)
    return _ARTICLE + word if definite else word


def _below_hundred(number: int, *, feminine: bool, definite: bool) -> str:
    """The ordinal of 1 to 99."""
    if number <= 10:
        return _unit(number, feminine=feminine, definite=definite)
    tens, unit = divmod(number, 10)
    if tens == 1:
        # 11 to 19: both halves agree in gender, only the first takes the article.
        first = _unit(unit, feminine=feminine, definite=definite, compound=True, teen=True)
        return f"{first} {'عشرة' if feminine else 'عشر'}"
    ten = (_ARTICLE if definite else "") + _TENS[tens]
    if not unit:
        return ten
    # 21 to 99: units first, joined to the tens by waw; both take the article.
    return f"{_unit(unit, feminine=feminine, definite=definite, compound=True)} و{ten}"


def _counting(count: int, *, definite: bool) -> str:
    """The cardinal of 11 to 99, as it stands before an accusative counted noun."""
    article = _ARTICLE if definite else ""
    tens, unit = divmod(count, 10)
    if tens == 1:
        first = {1: "أحد", 2: "اثنا"}.get(unit) or _CARDINALS[unit]
        return f"{article}{first} عشر"
    if not unit:
        return article + _TENS[tens]
    first = {1: "واحد", 2: "اثنان"}.get(unit) or _CARDINALS[unit]
    return f"{article}{first} و{article}{_TENS[tens]}"


def _scaled(count: int, scale: _Scale, *, definite: bool) -> str:
    """The cardinal of ``count`` (1 to 999) thousands, millions or billions.

    The counted noun follows the classical rules: singular for 1, dual for 2,
    a genitive plural after 3 to 10, an accusative singular after 11 to 99 and
    a genitive singular after a round hundred.  A definite number puts the
    article where each construction takes it: on the counted noun of a
    genitive construct (``ثلاثة الآلاف``, ``مئة الألف``) and on the number
    words otherwise (``الأحد عشر ألفًا``, ``الواحد والعشرون ألفًا``).
    """
    article = _ARTICLE if definite else ""
    hundreds, rest = divmod(count, 100)
    round_hundreds = f"{_HUNDREDS_CONSTRUCT[hundreds]} {article}{scale.singular}"
    if not rest:
        return round_hundreds
    if rest == 1:
        tail = article + scale.singular
    elif rest == 2:
        tail = article + scale.dual
    elif rest <= 10:
        tail = f"{_CARDINALS[rest]} {article}{scale.plural}"
    else:
        tail = f"{_counting(rest, definite=definite)} {scale.accusative}"
    if not hundreds:
        return tail
    # 101 000 is "a hundred thousand and a thousand"; from 103 000 on the
    # hundred stands alone and the counted noun follows the last number.
    head = round_hundreds if rest <= 2 else article + _HUNDREDS[hundreds]
    return f"{head} و{tail}"


def _round_cardinal(number: int, *, definite: bool) -> list[str]:
    """The cardinal of a multiple of 100, one entry per coordinated part."""
    parts = []
    for scale in _SCALES:
        count, number = divmod(number, scale.value)
        if count:
            parts.append(_scaled(count, scale, definite=definite))
    if number:
        parts.append((_ARTICLE if definite else "") + _HUNDREDS[number // 100])
    return parts


def ordinal_words(value: int | str, *, gender: Gender = "masculine", definite: bool = True) -> str:
    """Spell ``value`` as an Arabic ordinal: ``ordinal_words(3)`` is ``"الثالث"``.

    ``gender`` is ``"masculine"`` or ``"feminine"`` (``"m"`` and ``"f"`` are
    accepted too) and must match the noun the ordinal describes:
    ``الطابق الثالث`` but ``الفاتورة الثالثة``.  ``definite=False`` drops the
    article for an indefinite noun: ``طابق ثالث``.

    From 1 to 99 the result is the ordinal proper: the irregular ``الأول`` and
    ``الثاني`` (``الأولى``, ``الثانية``), the compounds for 11 to 19 in which
    both halves agree in gender and only the first takes the article
    (``الحادي عشر``, ``الحادية عشرة``), the tens, which have a single form for
    both genders (``العشرون``), and the units joined to the tens by *waw* with
    the article on both (``الحادي والعشرون``, ``التاسعة والتسعون``).  The
    indefinite masculine of the defective forms is written with its *tanwin*:
    ``ثانٍ``, ``حادٍ وعشرون``.

    Arabic has no ordinal form for a hundred, a thousand or anything larger,
    so those keep their cardinal word, and the article when definite:
    ``المئة``, ``المئتان``, ``الألف``.  A value above 100 is therefore written
    as the cardinal of its hundreds and above, followed by *waw* and the
    ordinal of its last two digits::

        ordinal_words(125)                    # 'المئة والخامس والعشرون'
        ordinal_words(125, gender="f")        # 'المئة والخامسة والعشرون'
        ordinal_words(1234, definite=False)   # 'ألف ومئتان ورابع وثلاثون'

    The words are in the nominative case and use the spelling ``مئة``.
    Integer strings are accepted, in Latin, Arabic-Indic or Persian digits.

    Raises ``ValueError`` for zero, a negative number, a ``bool``, a
    ``float``, a string that is not an integer, any other non-integer value,
    an unknown ``gender``, and a value above 999,999,999,999
    (``MAX_ORDINAL_WORDS``).
    """
    number = _positive_int(value)
    feminine = _is_feminine(gender)
    definite = bool(definite)
    if number > MAX_ORDINAL_WORDS:
        raise ValueError(
            f"ordinal_words() spells values up to {MAX_ORDINAL_WORDS:,}, got {number:,}; "
            "use ordinal_short() for larger numbers."
        )
    round_part, last_two = number - number % 100, number % 100
    parts = _round_cardinal(round_part, definite=definite)
    if last_two:
        parts.append(_below_hundred(last_two, feminine=feminine, definite=definite))
    return " و".join(parts)


def ordinal_short(value: int | str, *, language: str | None = None) -> str:
    """Write ``value`` as the short ordinal of ``language``: ``1st``, ``الـ1``.

    ``language`` defaults to the active language.  English appends ``st``,
    ``nd``, ``rd`` or ``th`` (``11th``, ``22nd``, ``113th``).  Arabic has no
    ordinal suffix; it prefixes the digits with the definite article and a
    tatweel, ``الـ`` (``ARABIC_SHORT_ORDINAL_MARKER``), which reads as the
    definite ordinal whatever the gender of the noun: ``الذكرى الـ25``.  Any
    other language gets the digits alone.

    The digits honour the project's digit localization switch,
    ``RTL_ADMIN["LOCALIZE_CHANGELIST_DIGITS"]``, exactly as the numeric cells
    of a changelist do.  It is off by default, and the digits are Latin.  When
    it is on they are written in the numbering system of ``language``, which
    ``RTL_ADMIN["NUMERALS"]`` can override: ``ordinal_short(25,
    language="ar-eg")`` is then ``"الـ٢٥"``.

    Raises ``ValueError`` for the same invalid values as ``ordinal_words()``;
    there is no upper limit.
    """
    number = _positive_int(value)
    code = (language or get_language() or "en").replace("_", "-").lower()
    base = code.split("-", 1)[0]
    digits = str(number)
    if rtl_settings.LOCALIZE_CHANGELIST_DIGITS:
        digits = transliterate_digits(digits, numbering_system(language))
    if base == "ar":
        return ARABIC_SHORT_ORDINAL_MARKER + digits
    if base == "en":
        suffix = "th" if 11 <= number % 100 <= 13 else _ENGLISH_SUFFIXES.get(number % 10, "th")
        return digits + suffix
    return digits


class _OrdinalDisplay(Protocol):
    """A ``list_display`` callable, with the attributes the admin reads."""

    __name__: str
    short_description: _StrOrPromise
    admin_order_field: str

    def __call__(self, obj: Any) -> str | None: ...


def ordinal_display(
    field_name: str,
    gender: Gender = "masculine",
    *,
    definite: bool = True,
    description: _StrOrPromise | None = None,
) -> _OrdinalDisplay:
    """Return a ``ModelAdmin.list_display`` callable that spells an integer field.

    Put the result straight into ``list_display``::

        class FloorAdmin(admin.ModelAdmin):
            list_display = ("building", ordinal_display("number", gender="m"))

    The column shows ``ordinal_words()`` of ``field_name``, which may follow
    relations with ``__``.  ``gender`` and ``definite`` are passed on, so pick
    the gender of the noun the column stands for.  The words are Arabic in
    every interface language.

    The callable keeps the field's sorting through ``admin_order_field``, and
    its ``__name__`` is the field name, so the column keeps its
    ``column-<name>`` and ``field-<name>`` CSS classes.  ``description`` sets
    the column header; without it Django derives one from the field name.

    An empty field renders as the admin's empty value, and a value
    ``ordinal_words()`` rejects (zero, a negative number) is shown as it is
    rather than breaking the changelist.  It works with or without
    ``BidiSafeAdminMixin``.

    Raises ``ValueError`` for an empty ``field_name`` or an unknown ``gender``.
    """
    if not isinstance(field_name, str) or not field_name.strip():
        raise ValueError(f"ordinal_display() needs a field name, got {field_name!r}.")
    _is_feminine(gender)
    path = field_name.split(LOOKUP_SEP)

    def display(obj: Any) -> str | None:
        value = obj
        for name in path:
            value = getattr(value, name, None)
            if value is None:
                return None
        try:
            return ordinal_words(value, gender=gender, definite=definite)
        except ValueError:
            return str(value)

    display.__name__ = field_name
    column = cast("_OrdinalDisplay", display)
    column.admin_order_field = field_name
    if description is not None:
        column.short_description = description
    return column
