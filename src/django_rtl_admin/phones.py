"""Phone number normalization, validation and formatting for MENA regions.

Admin users in Gulf countries, Egypt and Jordan often paste or type phone
numbers with Arabic-Indic (``٠١٢٣٤٥٦٧٨٩``) or Persian (``۰۱۲۳۴۵۶۷۸۹``) digits,
Unicode bidi controls, spaces, dashes, dots, parentheses, ``00`` or ``+``
international prefixes and local trunk zeros.

This module ships compact built-in numbering rules for Saudi Arabia (``SA``),
the United Arab Emirates (``AE``), Kuwait (``KW``), Qatar (``QA``), Bahrain
(``BH``), Oman (``OM``), Egypt (``EG``) and Jordan (``JO``) with no extra
runtime dependency.  When the optional ``phonenumbers`` package is installed,
parsing, validation and international display formatting delegate to it
instead, after the same digit transliteration, bidi stripping and letter
rejection.
"""

from __future__ import annotations

import importlib
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext

from .bidi import isolate, strip_isolates
from .formatting import transliterate_digits

if TYPE_CHECKING:
    from collections.abc import Collection

phonenumbers: Any
try:  # pragma: no cover - optional dependency
    phonenumbers = importlib.import_module("phonenumbers")
    HAS_PHONENUMBERS = True
except ImportError:  # pragma: no cover
    phonenumbers = None
    HAS_PHONENUMBERS = False


@dataclass(frozen=True)
class RegionRule:
    """Built-in national numbering plan for one supported region."""

    region: str
    country_code: str
    trunk_prefix: str
    mobile_patterns: tuple[tuple[int, tuple[str, ...]], ...]
    landline_patterns: tuple[tuple[int, tuple[str, ...]], ...]

    @property
    def national_lengths(self) -> tuple[int, ...]:
        """Valid national significant number lengths for this region."""
        return tuple(
            sorted({length for length, _ in (*self.mobile_patterns, *self.landline_patterns)})
        )

    @property
    def mobile_prefixes(self) -> tuple[str, ...]:
        """Mobile prefixes (without country code or trunk zero)."""
        return tuple(prefix for _, prefixes in self.mobile_patterns for prefix in prefixes)

    def is_mobile(self, nsn: str) -> bool:
        """Return ``True`` when ``nsn`` matches a mobile pattern for this region."""
        return any(
            len(nsn) == length and nsn.startswith(prefixes)
            for length, prefixes in self.mobile_patterns
        )

    def is_landline(self, nsn: str) -> bool:
        """Return ``True`` when ``nsn`` matches a landline pattern for this region."""
        return any(
            len(nsn) == length and nsn.startswith(prefixes)
            for length, prefixes in self.landline_patterns
        )


#: Built-in rules for the eight supported Gulf, Egypt and Jordan regions.
REGION_RULES: dict[str, RegionRule] = {
    "SA": RegionRule(
        region="SA",
        country_code="966",
        trunk_prefix="0",
        mobile_patterns=((9, ("50", "51", "53", "54", "55", "56", "57", "58", "59")),),
        landline_patterns=((9, ("11", "12", "13", "14", "16", "17")),),
    ),
    "AE": RegionRule(
        region="AE",
        country_code="971",
        trunk_prefix="0",
        mobile_patterns=((9, ("50", "52", "54", "55", "56", "58")),),
        landline_patterns=((8, ("2", "3", "4", "6", "7", "9")),),
    ),
    "KW": RegionRule(
        region="KW",
        country_code="965",
        trunk_prefix="",
        mobile_patterns=((8, ("41", "5", "6", "9")),),
        landline_patterns=((8, ("2",)),),
    ),
    "QA": RegionRule(
        region="QA",
        country_code="974",
        trunk_prefix="",
        mobile_patterns=((8, ("3", "5", "6", "7")),),
        landline_patterns=((8, ("4",)),),
    ),
    "BH": RegionRule(
        region="BH",
        country_code="973",
        trunk_prefix="",
        mobile_patterns=((8, ("3", "66")),),
        landline_patterns=((8, ("1", "65", "77")),),
    ),
    "OM": RegionRule(
        region="OM",
        country_code="968",
        trunk_prefix="",
        mobile_patterns=((8, ("7", "9")),),
        landline_patterns=((8, ("2",)),),
    ),
    "EG": RegionRule(
        region="EG",
        country_code="20",
        trunk_prefix="0",
        mobile_patterns=((10, ("10", "11", "12", "15")),),
        landline_patterns=(
            (
                9,
                (
                    "2",
                    "13",
                    "40",
                    "45",
                    "46",
                    "47",
                    "48",
                    "50",
                    "55",
                    "57",
                    "62",
                    "64",
                    "65",
                    "66",
                    "68",
                    "69",
                    "82",
                    "84",
                    "86",
                    "88",
                    "92",
                    "93",
                    "95",
                    "96",
                    "97",
                ),
            ),
            (8, ("3",)),
        ),
    ),
    "JO": RegionRule(
        region="JO",
        country_code="962",
        trunk_prefix="0",
        mobile_patterns=((9, ("77", "78", "79")),),
        landline_patterns=((8, ("2", "3", "5", "6")),),
    ),
}

#: ISO 3166-1 alpha-2 codes covered by the built-in rules.
SUPPORTED_REGIONS: tuple[str, ...] = tuple(REGION_RULES)

# Longest country calling codes first so prefix matching stays unambiguous.
_BY_COUNTRY_CODE: tuple[tuple[str, RegionRule], ...] = tuple(
    sorted(
        ((rule.country_code, rule) for rule in REGION_RULES.values()),
        key=lambda item: len(item[0]),
        reverse=True,
    )
)

# Formatting characters stripped alongside Unicode whitespace: ASCII/Unicode
# dashes, dots and parentheses.
_STRIPPED_PUNCTUATION = frozenset("-.()\u2010\u2011\u2012\u2013\u2014\u2212")
_CLEAN_PHONE_RE = re.compile(r"^\+?[0-9]+$")


@dataclass(frozen=True)
class _ParsedPhone:
    e164: str
    region: str
    is_mobile: bool


def _normalize_region(region: str) -> str:
    if not isinstance(region, str) or not region.strip():
        raise ValueError(f"Unsupported region {region!r}.")
    return region.strip().upper()


def _normalize_regions(regions: Collection[str] | str | None) -> tuple[str, ...] | None:
    if regions is None:
        return None
    if isinstance(regions, str):
        return (_normalize_region(regions),)
    normalized = tuple(_normalize_region(code) for code in regions)
    if not normalized:
        raise ValueError("regions must not be empty.")
    return normalized


def _clean_phone_input(value: str) -> str:
    """Strip bidi controls and separators, convert digits to ASCII, reject letters."""
    if not isinstance(value, str):
        raise ValueError(f"Phone number must be a string, got {type(value).__name__}.")
    text = transliterate_digits(strip_isolates(value), "latn")
    cleaned = "".join(ch for ch in text if not ch.isspace() and ch not in _STRIPPED_PUNCTUATION)
    if not cleaned or not _CLEAN_PHONE_RE.fullmatch(cleaned):
        raise ValueError(f"Invalid phone number: {value!r}.")
    if cleaned.startswith("00"):
        rest = cleaned[2:]
        if not rest or rest.startswith("0"):
            raise ValueError(f"Invalid phone number: {value!r}.")
        return "+" + rest
    if cleaned.startswith("+") and cleaned[1:].startswith("0"):
        raise ValueError(f"Invalid phone number: {value!r}.")
    return cleaned


def _parse_builtin_for_rule(nsn: str, rule: RegionRule) -> _ParsedPhone | None:
    candidate = (
        nsn[len(rule.trunk_prefix) :]
        if rule.trunk_prefix and nsn.startswith(rule.trunk_prefix)
        else nsn
    )
    if rule.is_mobile(candidate):
        return _ParsedPhone(f"+{rule.country_code}{candidate}", rule.region, True)
    if rule.is_landline(candidate):
        return _ParsedPhone(f"+{rule.country_code}{candidate}", rule.region, False)
    return None


def _parse_builtin(cleaned: str, default_region: str | None) -> _ParsedPhone:
    if cleaned.startswith("+"):
        digits = cleaned[1:]
        for code, candidate_rule in _BY_COUNTRY_CODE:
            if digits.startswith(code):
                parsed = _parse_builtin_for_rule(digits[len(code) :], candidate_rule)
                if parsed is not None:
                    return parsed
                raise ValueError(f"Invalid {candidate_rule.region} phone number.")
        raise ValueError("Unsupported or invalid country calling code.")

    if default_region is None:
        raise ValueError("Phone number is missing a country calling code.")
    region = _normalize_region(default_region)
    rule = REGION_RULES.get(region)
    if rule is None:
        raise ValueError(f"Unsupported region {default_region!r}.")

    parsed = _parse_builtin_for_rule(cleaned, rule)
    if parsed is not None:
        return parsed
    # Match phonenumbers: accept the default region's own country code without '+'.
    if cleaned.startswith(rule.country_code):
        parsed = _parse_builtin_for_rule(cleaned[len(rule.country_code) :], rule)
        if parsed is not None:
            return parsed
    raise ValueError(f"Invalid {rule.region} phone number.")


def _parse_with_phonenumbers(cleaned: str, default_region: str | None) -> _ParsedPhone:
    if cleaned.startswith("+"):
        region_arg: str | None = None
    else:
        if default_region is None:
            raise ValueError("Phone number is missing a country calling code.")
        region_arg = _normalize_region(default_region)
    try:
        parsed = phonenumbers.parse(cleaned, region_arg)
    except phonenumbers.NumberParseException as exc:
        raise ValueError(f"Invalid phone number: {exc}") from None
    if not phonenumbers.is_valid_number(parsed):
        raise ValueError("Invalid phone number.")
    e164: str = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    region: str = phonenumbers.region_code_for_number(parsed) or ""
    num_type = phonenumbers.number_type(parsed)
    mobile_types = (
        phonenumbers.PhoneNumberType.MOBILE,
        phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE,
    )
    return _ParsedPhone(e164=e164, region=region, is_mobile=num_type in mobile_types)


def _parse_phone(cleaned: str, default_region: str | None) -> _ParsedPhone:
    if phonenumbers is not None:
        return _parse_with_phonenumbers(cleaned, default_region)
    return _parse_builtin(cleaned, default_region)


def _resolve_phone(
    value: str,
    *,
    default_region: str | None = None,
    regions: Collection[str] | str | None = None,
    mobile_only: bool = False,
) -> _ParsedPhone:
    try:
        cleaned = _clean_phone_input(value)
    except ValueError:
        raise ValidationError(gettext("Enter a valid phone number."), code="invalid") from None

    allowed = _normalize_regions(regions)

    if cleaned.startswith("+"):
        try:
            parsed = _parse_phone(cleaned, None)
        except ValueError:
            raise ValidationError(gettext("Enter a valid phone number."), code="invalid") from None
        if allowed is not None and parsed.region not in allowed:
            raise ValidationError(
                gettext("Phone numbers from this region are not allowed."),
                code="invalid_region",
            )
        if mobile_only and not parsed.is_mobile:
            raise ValidationError(gettext("Enter a valid mobile phone number."), code="mobile_only")
        return parsed

    candidates: tuple[str, ...]
    if default_region is not None:
        normalized_default = _normalize_region(default_region)
        if allowed is None:
            candidates = (normalized_default,)
        elif normalized_default in allowed:
            candidates = (
                normalized_default,
                *(code for code in allowed if code != normalized_default),
            )
        else:
            candidates = allowed
    elif allowed is not None:
        candidates = allowed
    else:
        candidates = SUPPORTED_REGIONS

    saw_landline = False
    for candidate in candidates:
        try:
            parsed = _parse_phone(cleaned, candidate)
        except ValueError:
            continue
        if allowed is not None and parsed.region not in allowed:
            continue
        if mobile_only and not parsed.is_mobile:
            saw_landline = True
            continue
        return parsed

    if saw_landline:
        raise ValidationError(gettext("Enter a valid mobile phone number."), code="mobile_only")
    raise ValidationError(gettext("Enter a valid phone number."), code="invalid")


def normalize_phone(value: str, *, default_region: str = "SA") -> str:
    """Normalize a phone number to E.164 (for example ``"+966501234567"``).

    Converts Arabic-Indic and Persian digits with
    :func:`~django_rtl_admin.formatting.transliterate_digits`, removes Unicode
    ``Bidi_Control`` characters, whitespace, dashes, dots and parentheses,
    accepts ``+`` and ``00`` international prefixes as well as the local trunk
    ``0``, and rejects letters.

    Uses the optional ``phonenumbers`` package when installed; otherwise uses
    the built-in rules for ``SA``, ``AE``, ``KW``, ``QA``, ``BH``, ``OM``,
    ``EG`` and ``JO``.  Raises :class:`ValueError` when the number cannot be
    normalized to a valid E.164 phone number.
    """
    cleaned = _clean_phone_input(value)
    return _parse_phone(cleaned, default_region).e164


def validate_phone(
    value: str,
    *,
    regions: Collection[str] | str | None = None,
    mobile_only: bool = False,
) -> None:
    """Validate a phone number, raising :class:`ValidationError` if invalid.

    Error messages are translated through Django's active language catalog.
    Pass ``regions`` (for example ``("SA", "AE")``) to restrict accepted
    countries, and ``mobile_only=True`` to reject landlines.
    """
    _resolve_phone(value, regions=regions, mobile_only=mobile_only)


def _group_digits(digits: str, sizes: tuple[int, ...]) -> str:
    parts: list[str] = []
    pos = 0
    for size in sizes:
        parts.append(digits[pos : pos + size])
        pos += size
    return " ".join(parts)


def _format_builtin_e164(rule: RegionRule, nsn: str) -> str:
    if rule.region in ("KW", "QA", "BH", "OM"):
        grouped = _group_digits(nsn, (4, 4))
    elif rule.region == "SA":
        grouped = _group_digits(nsn, (2, 3, 4))
    elif rule.region in ("AE", "JO"):
        grouped = _group_digits(nsn, (2, 3, 4) if len(nsn) == 9 else (1, 3, 4))
    elif len(nsn) == 10:  # EG mobile
        grouped = _group_digits(nsn, (2, 4, 4))
    elif len(nsn) == 8:  # EG Alexandria landline
        grouped = _group_digits(nsn, (1, 3, 4))
    elif nsn.startswith("2"):  # EG Cairo/Giza landline
        grouped = _group_digits(nsn, (1, 4, 4))
    else:  # EG other regional landlines
        grouped = _group_digits(nsn, (2, 3, 4))
    return f"+{rule.country_code} {grouped}"


def _format_phone_text(value: Any, *, default_region: str | None = None) -> Any:
    """Return a country-grouped display string, or the original value on failure."""
    if value is None:
        return ""
    text = value if isinstance(value, str) else str(value)
    if not text.strip():
        return ""
    try:
        cleaned = _clean_phone_input(text)
    except ValueError:
        return value if isinstance(value, str) else text

    if phonenumbers is not None:
        region_arg = (
            None
            if cleaned.startswith("+")
            else (_normalize_region(default_region) if default_region is not None else None)
        )
        if cleaned.startswith("+") or region_arg is not None:
            try:
                parsed = phonenumbers.parse(cleaned, region_arg)
                if phonenumbers.is_valid_number(parsed):
                    return str(
                        phonenumbers.format_number(
                            parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL
                        )
                    )
            except phonenumbers.NumberParseException:
                pass
        return value if isinstance(value, str) else text

    try:
        parsed_builtin = _parse_builtin(cleaned, default_region)
    except ValueError:
        return value if isinstance(value, str) else text
    rule = REGION_RULES[parsed_builtin.region]
    nsn = parsed_builtin.e164[1 + len(rule.country_code) :]
    return _format_builtin_e164(rule, nsn)


def format_phone_display(value: Any, *, default_region: str | None = None) -> str:
    """Format an E.164 phone number grouped by country and wrapped in LTR isolation.

    Wrapping the formatted number in U+2066 (LRI) ... U+2069 (PDI) keeps the
    leading ``+`` and digit groups in left-to-right order inside Arabic prose.
    Unrecognized or invalid inputs are returned as LTR-isolated text; ``None``
    and empty strings return ``""``.
    """
    formatted = _format_phone_text(value, default_region=default_region)
    if not formatted:
        return ""
    return isolate(str(formatted), direction="ltr")


class PhoneNumberField(forms.CharField):
    """Form field that cleans regional phone input to E.164.

    Renders a text input with ``dir="ltr"``, ``inputmode="tel"`` and
    ``autocomplete="tel"`` so phone numbers stay left-to-right and trigger the
    telephone keypad inside an RTL admin form.
    """

    def __init__(
        self,
        *,
        default_region: str | None = None,
        regions: Collection[str] | str | None = None,
        mobile_only: bool = False,
        **kwargs: Any,
    ) -> None:
        normalized_regions = _normalize_regions(regions)
        if default_region is not None:
            resolved_default = _normalize_region(default_region)
        elif normalized_regions is not None:
            resolved_default = normalized_regions[0]
        else:
            resolved_default = "SA"
        self.default_region: str = resolved_default
        self.regions: tuple[str, ...] | None = normalized_regions
        self.mobile_only: bool = mobile_only
        super().__init__(**kwargs)

    def widget_attrs(self, widget: forms.Widget) -> dict[str, Any]:
        attrs = super().widget_attrs(widget)
        for key, value in (
            ("dir", "ltr"),
            ("inputmode", "tel"),
            ("autocomplete", "tel"),
        ):
            if key not in widget.attrs:
                attrs[key] = value
        return attrs

    def to_python(self, value: Any) -> str | None:
        text = super().to_python(value)
        if text in self.empty_values or not isinstance(text, str):
            return text
        try:
            return _resolve_phone(
                text,
                default_region=self.default_region,
                regions=self.regions,
                mobile_only=self.mobile_only,
            ).e164
        except ValidationError:
            return text

    def validate(self, value: Any) -> None:
        super().validate(value)
        if value in self.empty_values:
            return
        _resolve_phone(
            value,
            default_region=self.default_region,
            regions=self.regions,
            mobile_only=self.mobile_only,
        )
