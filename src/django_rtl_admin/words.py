"""Spell out numbers and money in Modern Standard Arabic."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Context, Decimal, InvalidOperation
from typing import Literal

Gender = Literal["masculine", "feminine"]

_LIMIT = 10**15
_WA = " و"
# Indexed by the gender of the *counted noun*, not the numeral itself.
_UNITS = {
    "masculine": (
        "",
        "واحد",
        "اثنان",
        "ثلاثة",
        "أربعة",
        "خمسة",
        "ستة",
        "سبعة",
        "ثمانية",
        "تسعة",
        "عشرة",
    ),
    "feminine": ("", "واحدة", "اثنتان", "ثلاث", "أربع", "خمس", "ست", "سبع", "ثمانٍ", "تسع", "عشر"),
}
_TENS = ("", "", "عشرون", "ثلاثون", "أربعون", "خمسون", "ستون", "سبعون", "ثمانون", "تسعون")
_HUNDREDS = (
    "",
    "مائة",
    "مائتان",
    "ثلاثمائة",
    "أربعمائة",
    "خمسمائة",
    "ستمائة",
    "سبعمائة",
    "ثمانمائة",
    "تسعمائة",
)
_ORDINALS = {
    "masculine": (
        "صفر",
        "أول",
        "ثاني",
        "ثالث",
        "رابع",
        "خامس",
        "سادس",
        "سابع",
        "ثامن",
        "تاسع",
        "عاشر",
    ),
    "feminine": (
        "صفر",
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
    ),
}


@dataclass(frozen=True)
class _Noun:
    singular: str
    dual: str
    plural: str
    gender: Gender = "masculine"
    accusative: str | None = None

    def singular_accusative(self) -> str:
        if self.accusative is not None:
            return self.accusative
        stem = self.singular
        # After a joining consonant a final, otherwise unseated hamza gets
        # a yeh seat before the support alif: شيء -> شيئًا (but جزء -> جزءًا).
        if len(stem) > 1 and stem.endswith("ء") and stem[-2] in "بتثجحخسشصضطظعغفقكلمنهي":
            stem = f"{stem[:-1]}ئ"
        # Tanwin needs a supporting alif except after these endings.
        alif = "" if stem.endswith(("ة", "ى", "ا", "أ", "اء")) else "ا"
        return f"{stem}ً{alif}"


_SCALES = (
    (10**12, _Noun("تريليون", "تريليونان", "تريليونات")),
    (10**9, _Noun("مليار", "ملياران", "مليارات")),
    (10**6, _Noun("مليون", "مليونان", "ملايين")),
    (10**3, _Noun("ألف", "ألفان", "آلاف")),
)


@dataclass(frozen=True)
class _Currency:
    major: _Noun
    minor: _Noun
    minor_digits: int = 2


_RIYAL = _Noun("ريال", "ريالان", "ريالات")
_DIRHAM = _Noun("درهم", "درهمان", "دراهم")
_DINAR = _Noun("دينار", "ديناران", "دنانير")
_FILS = _Noun("فلس", "فلسان", "فلوس")
_CURRENCIES = {
    "SAR": _Currency(_RIYAL, _Noun("هللة", "هللتان", "هللات", "feminine")),
    "AED": _Currency(_DIRHAM, _FILS),
    "KWD": _Currency(_DINAR, _FILS, 3),
    "QAR": _Currency(_RIYAL, _DIRHAM),
    "BHD": _Currency(_DINAR, _FILS, 3),
    "OMR": _Currency(_RIYAL, _Noun("بيسة", "بيستان", "بيسات", "feminine"), 3),
    "EGP": _Currency(_Noun("جنيه", "جنيهان", "جنيهات"), _Noun("قرش", "قرشان", "قروش")),
    "JOD": _Currency(_DINAR, _FILS, 3),
    "USD": _Currency(_Noun("دولار", "دولاران", "دولارات"), _Noun("سنت", "سنتان", "سنتات")),
}


def _gender(value: object) -> Gender:
    if value == "masculine":
        return "masculine"
    if value == "feminine":
        return "feminine"
    raise ValueError("gender must be 'masculine' or 'feminine'")


def _article(word: str, definite: bool) -> str:
    return f"ال{word}" if definite else word


def _under_hundred(value: int, gender: Gender, *, construct: bool, definite: bool) -> str:
    units = _UNITS[gender]
    if value <= 10:
        word = units[value]
        if value == 8 and gender == "feminine" and (construct or definite):
            word = "ثماني"
        return _article(word, definite)

    feminine = gender == "feminine"
    if value < 20:
        teen = value - 10
        if teen == 1:
            first = "إحدى" if feminine else "أحد"
        elif teen == 2:
            first = "اثنتا" if feminine else "اثنا"
        elif teen == 8 and feminine:
            first = "ثماني"
        else:
            first = units[teen]
        return f"{_article(first, definite)} {'عشرة' if feminine else 'عشر'}"

    tens, unit = divmod(value, 10)
    ones = "ثماني" if unit == 8 and feminine and definite else units[unit]
    return _WA.join(_article(word, definite) for word in (ones, _TENS[tens]) if word)


def _under_thousand(
    value: int, gender: Gender, *, construct: bool = False, definite: bool = False
) -> str:
    hundreds, rest = divmod(value, 100)
    parts = []
    if hundreds:
        # A dual loses its final nun in a construct (مائتا ريال, مائتا ألف).
        word = "مائتا" if hundreds == 2 and not rest and construct else _HUNDREDS[hundreds]
        parts.append(_article(word, definite))
    if rest:
        parts.append(_under_hundred(rest, gender, construct=construct, definite=definite))
    return _WA.join(parts)


def _count_group(
    value: int, noun: _Noun, *, complement: str = "", scale: bool = False, definite: bool = False
) -> str:
    """Spell 0–999 with a counted noun; a scale may itself count a currency."""
    hundreds, rest = divmod(value, 100)
    if rest in (1, 2):
        form = noun.singular if rest == 1 else noun.dual
        if rest == 2 and complement:
            form = form[:-1]  # ألفان -> ألفا before the currency noun
        tail = _article(form, definite)
        if complement:
            tail = f"{tail} {complement}"
        if not scale:
            tail = f"{tail} {_UNITS[noun.gender][rest]}"
        if not hundreds:
            return tail
        # Keep the magnitude on the hundreds part of a scale group, but
        # attach the currency only to the tail: مائة ألف وألفا ريال.
        head_value = hundreds * 100
        if scale:
            head = _count_group(head_value, noun, definite=definite)
        else:
            head = _under_thousand(head_value, noun.gender, definite=definite)
        return _WA.join((head, tail))

    if 3 <= rest <= 10:
        form = noun.plural
    elif rest >= 11 and not complement:
        form = noun.singular_accusative()
    else:
        form = noun.singular
    noun_construct = rest <= 10
    if complement:
        form = f"{form} {complement}"
    elif definite and noun_construct:
        form = _article(form, True)
    number = (
        _under_thousand(
            value, noun.gender, construct=True, definite=definite and not noun_construct
        )
        if value
        else "صفر"
    )
    return f"{number} {form}"


def _cardinal(
    value: int, gender: Gender, *, noun: _Noun | None = None, definite: bool = False
) -> str:
    parts = []
    for size, scale in _SCALES:
        group, value = divmod(value, size)
        if group:
            complement = noun.singular if noun is not None and not value else ""
            parts.append(
                _count_group(group, scale, complement=complement, scale=True, definite=definite)
            )
    if value or not parts:
        if noun is not None:
            parts.append(_count_group(value, noun))
        else:
            parts.append(_under_thousand(value, gender, definite=definite) if value else "صفر")
    return _WA.join(parts)


def _ordinal(value: int, gender: Gender) -> str:
    high, rest = divmod(value, 100)
    parts = [_cardinal(high * 100, gender, definite=True)] if high else []
    ordinals = _ORDINALS[gender]
    if rest <= 10:
        if rest or not high:
            parts.append(f"ال{ordinals[rest]}")
    elif rest < 20:
        unit = rest - 10
        first = ("حادي" if gender == "masculine" else "حادية") if unit == 1 else ordinals[unit]
        parts.append(f"ال{first} {'عشر' if gender == 'masculine' else 'عشرة'}")
    else:
        tens, unit = divmod(rest, 10)
        if unit:
            first = ("حادي" if gender == "masculine" else "حادية") if unit == 1 else ordinals[unit]
            parts.append(f"ال{first}")
        parts.append(f"ال{_TENS[tens]}")
    return _WA.join(parts)


def number_to_arabic_words(
    value: int, *, gender: Gender = "masculine", ordinal: bool = False
) -> str:
    """Return Arabic words for an integer with magnitude less than 10**15.

    Gender refers to the noun being counted or ranked: for example, the
    cardinal for three is «ثلاثة» for a masculine noun and «ثلاث» for a
    feminine noun. Ordinals are definite (e.g. «الثالثة»); zero is «الصفر»
    for either gender. Negative numbers start with «سالب». Invalid values or
    options raise ValueError.
    """
    if isinstance(value, bool) or not isinstance(value, int) or not -_LIMIT < value < _LIMIT:
        raise ValueError("value must be an integer with magnitude less than 10**15")
    gender = _gender(gender)
    if not isinstance(ordinal, bool):
        raise ValueError("ordinal must be a boolean")
    words = (_ordinal if ordinal else _cardinal)(abs(value), gender)
    return f"سالب {words}" if value < 0 else words


_NUMERIC = re.compile(
    r"[+-]?(?:(?:[0-9]+|[0-9]{1,3}(?:٬[0-9]{3})+)(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?"
)
_NUMERIC_TRANSLATION = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٫−", "01234567890123456789.-")


def _decimal(value: Decimal | int | str) -> Decimal:
    if isinstance(value, str):
        value = value.strip().translate(_NUMERIC_TRANSLATION)
        if not _NUMERIC.fullmatch(value):
            raise ValueError("invalid numeric string")
        try:
            return Decimal(value.replace("٬", ""))
        except InvalidOperation as exc:
            raise ValueError("invalid numeric string") from exc
    if isinstance(value, bool) or not isinstance(value, (Decimal, int)):
        raise ValueError("amount must be a Decimal, integer or numeric string")
    return value if isinstance(value, Decimal) else Decimal(value)


def _custom_noun(value: object) -> _Noun:
    if not isinstance(value, Mapping):
        raise ValueError("major and minor must be dictionaries of noun forms")

    def form(key: str) -> str:
        text = value.get(key)
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"{key} must be a nonempty string")
        return text.strip()

    return _Noun(
        form("singular"),
        form("dual"),
        form("plural"),
        gender=_gender(value.get("gender")),
        accusative=form("accusative") if "accusative" in value else None,
    )


def _currency(value: str | Mapping[str, object]) -> _Currency:
    if isinstance(value, str):
        try:
            return _CURRENCIES[value.strip().upper()]
        except KeyError:
            raise ValueError(f"unsupported currency: {value!r}") from None
    if not isinstance(value, Mapping):
        raise ValueError("currency must be a code or a dictionary of currency data")
    digits = value.get("minor_digits")
    if isinstance(digits, bool) or not isinstance(digits, int) or not 0 <= digits <= 15:
        raise ValueError("minor_digits must be an integer from 0 to 15")
    return _Currency(_custom_noun(value.get("major")), _custom_noun(value.get("minor")), digits)


def amount_to_arabic_words(
    value: Decimal | int | str, currency: str | Mapping[str, object] = "SAR", *, only: bool = True
) -> str:
    """Return Arabic money words, rounded half-up to the currency's minor digits.

    The currency can be a supported ISO code or a dictionary with ``minor_digits``
    and ``major`` / ``minor`` noun dictionaries. Each noun needs ``singular``,
    ``dual``, ``plural`` and ``gender``; ``accusative`` can override the regular
    singular accusative form. Zero units are omitted unless both parts are zero,
    in which case the result names the major unit. The output ends in «فقط» by
    default. Invalid inputs (including an out-of-range rounded total) raise
    ValueError.
    """
    if not isinstance(only, bool):
        raise ValueError("only must be a boolean")
    spec = _currency(currency)
    amount = _decimal(value)
    if not amount.is_finite() or amount.copy_abs() >= _LIMIT:
        raise ValueError("amount must be finite with magnitude less than 10**15")

    digits = spec.minor_digits
    # Enough precision for the largest amount, the minor digits and a carry.
    # An explicit context isolates rounding from the caller's decimal settings.
    context = Context(prec=16 + digits, rounding=ROUND_HALF_UP, traps=[InvalidOperation])
    quantum = Decimal((0, (1,), -digits))
    rounded = amount.quantize(quantum, context=context)
    major, minor = divmod(int(rounded.copy_abs().scaleb(digits, context=context)), 10**digits)
    if major >= _LIMIT:
        raise ValueError("rounded amount must have magnitude less than 10**15")

    parts = []
    if major or not minor:
        parts.append(_cardinal(major, spec.major.gender, noun=spec.major))
    if minor:
        parts.append(_cardinal(minor, spec.minor.gender, noun=spec.minor))
    words = _WA.join(parts)
    if rounded.is_signed() and (major or minor):
        words = f"سالب {words}"
    return f"{words} فقط" if only else words
