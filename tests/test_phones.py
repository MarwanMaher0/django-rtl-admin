"""Tests for regional phone normalization, validation, form field and display filter."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from django import forms
from django.core.exceptions import ValidationError
from django.template import Context, Template
from django.utils.safestring import mark_safe
from django.utils.translation import override as override_language

import django_rtl_admin
from django_rtl_admin import (
    PhoneNumberField,
    format_phone_display,
    normalize_phone,
    validate_phone,
)
from django_rtl_admin import phones as phones_module
from django_rtl_admin.bidi import ALM, FSI, LRE, LRI, LRM, PDF, PDI, RLI, RLM, RLO

# ---------------------------------------------------------------------------
# Valid normalization across all 8 countries (SA, AE, KW, QA, BH, OM, EG, JO)
# ---------------------------------------------------------------------------

VALID_CASES = [
    # Saudi Arabia (SA, +966) — mobile & landline
    ("0501234567", "SA", "+966501234567"),
    ("501234567", "SA", "+966501234567"),
    ("+966501234567", "SA", "+966501234567"),
    ("00966501234567", "SA", "+966501234567"),
    ("966501234567", "SA", "+966501234567"),
    ("+966 050 123 4567", "SA", "+966501234567"),
    ("(+966) 55-123-4567", "SA", "+966551234567"),
    ("059.123.4567", "SA", "+966591234567"),
    ("٠٥٠ ١٢٣ ٤٥٦٧", "SA", "+966501234567"),
    ("٠٠٩٦٦ ٥٣-١٢٣-٤٥٦٧", "SA", "+966531234567"),
    ("۰۵۴ ۱۲۳ ۴۵۶۷", "SA", "+966541234567"),
    ("+۹۶۶ ۵۸ ۱۲۳ ۴۵۶۷", "SA", "+966581234567"),
    (f"{LRI}+٩٦٦ ٥٦ ١٢٣ ٤٥٦٧{PDI}", "SA", "+966561234567"),
    (f"{RLM}{ALM}٠٥١\u2013١٢٣\u2014٤٥٦٧{LRM}", "SA", "+966511234567"),
    ("0112345678", "SA", "+966112345678"),
    ("+966 12 345 6789", "SA", "+966123456789"),
    ("00966 13 890 1234", "SA", "+966138901234"),
    ("٠١٤ ٢٣٤ ٥٦٧٨", "SA", "+966142345678"),
    ("016-234-5678", "SA", "+966162345678"),
    ("017 234 5678", "SA", "+966172345678"),
    # United Arab Emirates (AE, +971) — mobile (9) & landline (8)
    ("0501234567", "AE", "+971501234567"),
    ("521234567", "AE", "+971521234567"),
    ("+971 54 123 4567", "SA", "+971541234567"),
    ("00971 55 123 4567", "SA", "+971551234567"),
    ("٠٥٦ ١٢٣ ٤٥٦٧", "AE", "+971561234567"),
    ("۰۵۸ ۱۲۳ ۴۵۶۷", "ae", "+971581234567"),
    ("04 123 4567", "AE", "+97141234567"),
    ("+971 2 123 4567", "AE", "+97121234567"),
    ("٠٠٩٧١ ٣ ١٢٣ ٤٥٦٧", "SA", "+97131234567"),
    ("06-123-4567", "AE", "+97161234567"),
    ("07.123.4567", "AE", "+97171234567"),
    ("09 (123) 4567", "AE", "+97191234567"),
    # Kuwait (KW, +965) — mobile (8) & landline (8)
    ("51234567", "KW", "+96551234567"),
    ("+965 6123 4567", "SA", "+96561234567"),
    ("00965 9123 4567", "SA", "+96591234567"),
    ("41234567", "KW", "+96541234567"),
    ("٥١٢٣ ٤٥٦٧", "KW", "+96551234567"),
    ("۹۱۲۳ ۴۵۶۷", "KW", "+96591234567"),
    ("22401234", "KW", "+96522401234"),
    ("+965 2240 1234", "KW", "+96522401234"),
    (f"{FSI}٠٠٩٦٥ ٢٢٤٠ ١٢٣٤{PDI}", "SA", "+96522401234"),
    # Qatar (QA, +974) — mobile (8) & landline (8)
    ("33123456", "QA", "+97433123456"),
    ("+974 5512 3456", "SA", "+97455123456"),
    ("00974 6612 3456", "SA", "+97466123456"),
    ("٧٧١٢ ٣٤٥٦", "QA", "+97477123456"),
    ("۵۵۱۲ ۳۴۵۶", "QA", "+97455123456"),
    ("44123456", "QA", "+97444123456"),
    ("+974 4412 3456", "QA", "+97444123456"),
    # Bahrain (BH, +973) — mobile (8) & landline (8)
    ("39123456", "BH", "+97339123456"),
    ("+973 3312 3456", "SA", "+97333123456"),
    ("00973 6631 2345", "SA", "+97366312345"),
    ("٣٩١٢ ٣٤٥٦", "BH", "+97339123456"),
    ("۳۳۱۲ ۳۴۵۶", "BH", "+97333123456"),
    ("17123456", "BH", "+97317123456"),
    ("+973 1712 3456", "BH", "+97317123456"),
    ("65123456", "BH", "+97365123456"),
    # Oman (OM, +968) — mobile (8) & landline (8)
    ("92123456", "OM", "+96892123456"),
    ("+968 7912 3456", "SA", "+96879123456"),
    ("00968 9123 4567", "SA", "+96891234567"),
    ("٩٢١٢ ٣٤٥٦", "OM", "+96892123456"),
    ("۷۹۱۲ ۳۴۵۶", "OM", "+96879123456"),
    ("24123456", "OM", "+96824123456"),
    ("+968 2312 3456", "OM", "+96823123456"),
    # Egypt (EG, +20) — mobile (10) & landlines (Cairo 9, Alex 8, regional 9)
    ("01012345678", "EG", "+201012345678"),
    ("1112345678", "EG", "+201112345678"),
    ("+20 12 3456 7890", "SA", "+201234567890"),
    ("0020 15 1234 5678", "SA", "+201512345678"),
    ("+20 010 1234 5678", "EG", "+201012345678"),
    ("٠١٠ ١٢٣٤ ٥٦٧٨", "EG", "+201012345678"),
    ("۰۱۲ ۳۴۵۶ ۷۸۹۰", "EG", "+201234567890"),
    (f"{RLI}{LRE}+٢٠ (١٠) ١٢٣٤-٥٦٧٨{PDF}{PDI}", "SA", "+201012345678"),
    ("02 2345 6789", "EG", "+20223456789"),
    ("+20 2 2345 6789", "EG", "+20223456789"),
    ("03 456 7890", "EG", "+2034567890"),
    ("٠٠٢٠ ٣ ٤٥٦ ٧٨٩٠", "SA", "+2034567890"),
    ("050 234 5678", "EG", "+20502345678"),
    ("040-345-6789", "EG", "+20403456789"),
    # Jordan (JO, +962) — mobile (9) & landline (8)
    ("0791234567", "JO", "+962791234567"),
    ("781234567", "JO", "+962781234567"),
    ("+962 77 123 4567", "SA", "+962771234567"),
    ("00962 79 123 4567", "SA", "+962791234567"),
    ("٠٧٩ ١٢٣ ٤٥٦٧", "JO", "+962791234567"),
    ("۰۷۸ ۱۲۳ ۴۵۶۷", "JO", "+962781234567"),
    (f"{RLO}079 123 4567{PDF}", "JO", "+962791234567"),
    ("06 512 3456", "JO", "+96265123456"),
    ("+962 2 712 3456", "JO", "+96227123456"),
    ("00962 5 312 3456", "SA", "+96253123456"),
    ("03-234-5678", "JO", "+96232345678"),
]


@pytest.mark.parametrize(("raw", "region", "expected"), VALID_CASES)
def test_normalize_phone_valid_cases(raw, region, expected):
    assert normalize_phone(raw, default_region=region) == expected


# ---------------------------------------------------------------------------
# Invalid normalization cases across all 8 countries
# ---------------------------------------------------------------------------

INVALID_CASES = [
    # Invalid lengths (too short / too long)
    ("050123456", "SA"),  # SA mobile too short (8)
    ("96650123456", "SA"),  # SA bare country code, too short
    ("05012345678", "SA"),  # SA mobile too long (10)
    ("011234567", "SA"),  # SA landline too short (8)
    ("050123456", "AE"),  # AE mobile too short (8)
    ("0412345678", "AE"),  # AE landline too long (9)
    ("5123456", "KW"),  # KW too short (7)
    ("512345678", "KW"),  # KW too long (9)
    ("051234567", "KW"),  # KW has no trunk 0
    ("5512345", "QA"),  # QA too short (7)
    ("551234567", "QA"),  # QA too long (9)
    ("3912345", "BH"),  # BH too short (7)
    ("391234567", "BH"),  # BH too long (9)
    ("9212345", "OM"),  # OM too short (7)
    ("921234567", "OM"),  # OM too long (9)
    ("0101234567", "EG"),  # EG mobile too short (9)
    ("010123456789", "EG"),  # EG mobile too long (11)
    ("022345678", "EG"),  # EG Cairo landline too short (8)
    ("0345678901", "EG"),  # EG Alex landline too long (9)
    ("079123456", "JO"),  # JO mobile too short (8)
    ("0651234567", "JO"),  # JO landline too long (9)
    # Wrong prefixes
    ("0521234567", "SA"),  # SA 52 unassigned
    ("0152345678", "SA"),  # SA 15 invalid landline prefix
    ("0511234567", "AE"),  # AE 51 invalid mobile prefix
    ("081234567", "AE"),  # AE 8 invalid landline prefix
    ("31234567", "KW"),  # KW 3 invalid prefix
    ("88123456", "QA"),  # QA 8 invalid prefix
    ("21234567", "BH"),  # BH 2 invalid prefix
    ("51234567", "OM"),  # OM 5 invalid prefix
    ("01412345678", "EG"),  # EG 14 invalid mobile prefix
    ("0761234567", "JO"),  # JO 76 invalid mobile prefix
    ("045123456", "JO"),  # JO 4 invalid landline prefix
    # Letters & non-phone text
    ("050abc4567", "SA"),
    ("050-123-4567 ext 1", "SA"),
    ("call 0501234567", "SA"),
    ("هاتف ٠٥٠١٢٣٤٥٦٧", "SA"),
    ("شماره ۰۵۰۱۲۳۴۵۶۷", "SA"),
    ("+966-50-XYZ-4567", "SA"),
    # Malformed prefixes & disallowed punctuation
    ("", "SA"),
    ("   ", "SA"),
    (f"{LRI}{PDI}{RLM}", "SA"),
    ("+", "SA"),
    ("00", "SA"),
    ("+00966501234567", "SA"),
    ("000966501234567", "SA"),
    ("++966501234567", "SA"),
    ("50+1234567", "SA"),
    ("050/123/4567", "SA"),
    ("050#1234567", "SA"),
    ("+966 0050 123 4567", "SA"),
    # Unsupported country / region
    ("+442079460958", "SA"),
    ("0501234567", "ZZ"),
    ("0501234567", ""),
]


@pytest.mark.parametrize(("raw", "region"), INVALID_CASES)
def test_normalize_phone_invalid_cases(raw, region):
    with pytest.raises(ValueError):
        normalize_phone(raw, default_region=region)


def test_normalize_phone_rejects_non_string():
    with pytest.raises(ValueError):
        normalize_phone(966501234567)  # type: ignore[arg-type]


def test_normalize_phone_uses_existing_transliterate_digits(monkeypatch):
    called_with: list[tuple[str, str]] = []
    real_transliterate = phones_module.transliterate_digits

    def spy(text: str, to: str = "latn") -> str:
        called_with.append((text, to))
        return real_transliterate(text, to)

    monkeypatch.setattr(phones_module, "transliterate_digits", spy)
    assert normalize_phone("٠٥٠ ١٢٣ ٤٥٦٧") == "+966501234567"
    assert called_with == [("٠٥٠ ١٢٣ ٤٥٦٧", "latn")]


def test_region_rule_metadata_properties():
    assert set(phones_module.SUPPORTED_REGIONS) == {"SA", "AE", "KW", "QA", "BH", "OM", "EG", "JO"}
    assert phones_module.REGION_RULES["SA"].national_lengths == (9,)
    assert "50" in phones_module.REGION_RULES["SA"].mobile_prefixes
    assert phones_module.REGION_RULES["EG"].national_lengths == (8, 9, 10)


# ---------------------------------------------------------------------------
# validate_phone: regions, mobile_only, translated error messages (ar & en)
# ---------------------------------------------------------------------------

MOBILE_NUMBERS = [
    ("+966501234567", "SA"),
    ("+971501234567", "AE"),
    ("+96551234567", "KW"),
    ("+97455123456", "QA"),
    ("+97339123456", "BH"),
    ("+96892123456", "OM"),
    ("+201012345678", "EG"),
    ("+962791234567", "JO"),
]

LANDLINE_NUMBERS = [
    ("+966112345678", "SA"),
    ("+97141234567", "AE"),
    ("+96522401234", "KW"),
    ("+97444123456", "QA"),
    ("+97317123456", "BH"),
    ("+96824123456", "OM"),
    ("+20223456789", "EG"),
    ("+96265123456", "JO"),
]


@pytest.mark.parametrize(("number", "region"), MOBILE_NUMBERS)
def test_validate_phone_accepts_mobile_in_all_regions(number, region):
    validate_phone(number)
    validate_phone(number, regions=(region,), mobile_only=True)
    validate_phone(number, regions=region, mobile_only=True)


@pytest.mark.parametrize(("number", "region"), LANDLINE_NUMBERS)
def test_validate_phone_landline_and_mobile_only(number, region):
    validate_phone(number)
    validate_phone(number, regions=(region,))
    with pytest.raises(ValidationError) as exc_info:
        validate_phone(number, regions=(region,), mobile_only=True)
    assert exc_info.value.code == "mobile_only"


def test_validate_phone_local_numbers_and_regions():
    validate_phone("٠٥٠ ١٢٣ ٤٥٦٧")
    validate_phone("01012345678")
    validate_phone("0791234567")
    validate_phone("51234567")
    validate_phone("01012345678", regions=["EG"])

    with pytest.raises(ValidationError) as exc_info:
        validate_phone("01012345678", regions=["SA"])
    assert exc_info.value.code == "invalid"

    with pytest.raises(ValidationError) as exc_info:
        validate_phone("011 234 5678", regions=["SA"], mobile_only=True)
    assert exc_info.value.code == "mobile_only"

    with pytest.raises(ValidationError) as exc_info:
        validate_phone("+971501234567", regions=["SA"])
    assert exc_info.value.code == "invalid_region"

    with pytest.raises(ValueError):
        validate_phone("+966501234567", regions=[])


@pytest.mark.parametrize(
    ("call_kwargs", "value", "expected_code", "expected_en", "expected_ar"),
    [
        (
            {},
            "not-a-phone",
            "invalid",
            "Enter a valid phone number.",
            "أدخل رقم هاتف صحيحًا.",
        ),
        (
            {"mobile_only": True},
            "+966112345678",
            "mobile_only",
            "Enter a valid mobile phone number.",
            "أدخل رقم هاتف جوال صحيحًا.",
        ),
        (
            {"regions": ("SA",)},
            "+971501234567",
            "invalid_region",
            "Phone numbers from this region are not allowed.",
            "أرقام الهاتف من هذه المنطقة غير مسموح بها.",
        ),
    ],
)
def test_validate_phone_translated_messages_in_en_and_ar(
    call_kwargs, value, expected_code, expected_en, expected_ar
):
    with override_language("en"):
        with pytest.raises(ValidationError) as en_exc:
            validate_phone(value, **call_kwargs)
    assert en_exc.value.code == expected_code
    assert en_exc.value.messages == [expected_en]

    with override_language("ar"):
        with pytest.raises(ValidationError) as ar_exc:
            validate_phone(value, **call_kwargs)
    assert ar_exc.value.code == expected_code
    assert ar_exc.value.messages == [expected_ar]


# ---------------------------------------------------------------------------
# Mocked optional `phonenumbers` backend
# ---------------------------------------------------------------------------


def _make_fake_phonenumbers():
    class FakeNumberParseException(Exception):
        pass

    class FakeFormat:
        E164 = 0
        INTERNATIONAL = 1

    class FakeType:
        FIXED_LINE = 0
        MOBILE = 1
        FIXED_LINE_OR_MOBILE = 2

    records = {
        ("+966501234567", None): ("+966501234567", "+966 50 123 4567", "SA", FakeType.MOBILE, True),
        ("0501234567", "SA"): ("+966501234567", "+966 50 123 4567", "SA", FakeType.MOBILE, True),
        ("+966112345678", None): (
            "+966112345678",
            "+966 11 234 5678",
            "SA",
            FakeType.FIXED_LINE,
            True,
        ),
        ("+442079460958", None): (
            "+442079460958",
            "+44 20 7946 0958",
            "GB",
            FakeType.FIXED_LINE_OR_MOBILE,
            True,
        ),
        ("+966999999999", None): (
            "+966999999999",
            "+966 99 999 9999",
            "SA",
            FakeType.MOBILE,
            False,
        ),
        ("0501234567", "AE"): ("+966501234567", "+966 50 123 4567", "SA", FakeType.MOBILE, True),
    }

    fake = SimpleNamespace(
        NumberParseException=FakeNumberParseException,
        PhoneNumberFormat=FakeFormat,
        PhoneNumberType=FakeType,
    )

    def parse(text, region):
        key = (text, region)
        if key not in records:
            raise FakeNumberParseException("unparseable")
        e164, intl, reg, ntype, valid = records[key]
        return SimpleNamespace(e164=e164, intl=intl, region=reg, ntype=ntype, valid=valid)

    fake.parse = MagicMock(side_effect=parse)
    fake.is_valid_number = MagicMock(side_effect=lambda p: p.valid)
    fake.format_number = MagicMock(
        side_effect=lambda p, fmt: p.e164 if fmt == FakeFormat.E164 else p.intl
    )
    fake.region_code_for_number = MagicMock(side_effect=lambda p: p.region)
    fake.number_type = MagicMock(side_effect=lambda p: p.ntype)
    return fake


def test_phonenumbers_backend_used_when_installed(monkeypatch):
    fake_pn = _make_fake_phonenumbers()
    monkeypatch.setattr(phones_module, "phonenumbers", fake_pn)

    # Normalizes Arabic-Indic, strips bidi and delegates to phonenumbers.
    assert normalize_phone(f"{LRI}٠٥٠ ١٢٣ ٤٥٦٧{PDI}", default_region="SA") == "+966501234567"
    fake_pn.parse.assert_called_with("0501234567", "SA")

    # Supports non-MENA numbers when phonenumbers is installed.
    assert normalize_phone("0044 20 7946 0958") == "+442079460958"
    validate_phone("+442079460958", mobile_only=True)  # FIXED_LINE_OR_MOBILE counts as mobile

    # Still rejects letters BEFORE calling phonenumbers (no vanity alpha conversion).
    fake_pn.parse.reset_mock()
    with pytest.raises(ValueError):
        normalize_phone("050-ABC-4567", default_region="SA")
    fake_pn.parse.assert_not_called()

    # Invalid number according to phonenumbers.is_valid_number.
    with pytest.raises(ValueError):
        normalize_phone("+966999999999")

    # NumberParseException turns into ValueError / ValidationError.
    with pytest.raises(ValueError):
        normalize_phone("+9660000000")
    with pytest.raises(ValidationError) as exc_info:
        validate_phone("+9660000000")
    assert exc_info.value.code == "invalid"

    # Region & mobile_only checks work with phonenumbers.
    with pytest.raises(ValidationError) as exc_info:
        validate_phone("+442079460958", regions=("SA",))
    assert exc_info.value.code == "invalid_region"

    with pytest.raises(ValidationError) as exc_info:
        validate_phone("+966112345678", mobile_only=True)
    assert exc_info.value.code == "mobile_only"

    # Missing default_region for local number raises ValueError.
    with pytest.raises(ValueError):
        phones_module._parse_with_phonenumbers("0501234567", None)

    # Display formatting delegates to phonenumbers.PhoneNumberFormat.INTERNATIONAL.
    assert format_phone_display("+442079460958") == f"{LRI}+44 20 7946 0958{PDI}"
    assert format_phone_display("0501234567", default_region="SA") == f"{LRI}+966 50 123 4567{PDI}"
    assert format_phone_display("0501234567") == f"{LRI}0501234567{PDI}"
    assert format_phone_display("+966999999999") == f"{LRI}+966999999999{PDI}"
    assert format_phone_display("+9660000000") == f"{LRI}+9660000000{PDI}"

    # Local number whose detected region is outside allowed regions is rejected.
    with pytest.raises(ValidationError) as exc_info:
        validate_phone("0501234567", regions=("AE",))
    assert exc_info.value.code == "invalid"


# ---------------------------------------------------------------------------
# PhoneNumberField form field in a bound form
# ---------------------------------------------------------------------------


def test_phone_number_field_renders_ltr_tel_attributes():
    class ContactForm(forms.Form):
        phone = PhoneNumberField()

    html = str(ContactForm()["phone"])
    assert 'dir="ltr"' in html
    assert 'inputmode="tel"' in html
    assert 'autocomplete="tel"' in html


def test_phone_number_field_preserves_caller_widget_attrs():
    class CustomForm(forms.Form):
        phone = PhoneNumberField(
            widget=forms.TextInput(attrs={"autocomplete": "off", "class": "my-tel"})
        )

    html = str(CustomForm()["phone"])
    assert 'dir="ltr"' in html
    assert 'inputmode="tel"' in html
    assert 'autocomplete="off"' in html
    assert 'class="my-tel"' in html


def test_phone_number_field_in_bound_form():
    class ContactForm(forms.Form):
        phone = PhoneNumberField(max_length=16)

    form = ContactForm({"phone": "٠٠٩٦٦ (٥٠) ١٢٣-٤٥٦٧"})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["phone"] == "+966501234567"

    persian_form = ContactForm({"phone": "۰۵۵ ۱۲۳ ۴۵۶۷"})
    assert persian_form.is_valid(), persian_form.errors
    assert persian_form.cleaned_data["phone"] == "+966551234567"


def test_phone_number_field_regions_and_mobile_only():
    class GulfMobileForm(forms.Form):
        phone = PhoneNumberField(regions=("AE", "SA"), mobile_only=True)

    # First region ("AE") acts as the default for local input.
    local_ae = GulfMobileForm({"phone": "٠٥٠ ١٢٣ ٤٥٦٧"})
    assert local_ae.is_valid(), local_ae.errors
    assert local_ae.cleaned_data["phone"] == "+971501234567"

    # Explicit default_region inside regions takes precedence.
    class SaFirstForm(forms.Form):
        phone = PhoneNumberField(default_region="SA", regions=("AE", "SA"))

    local_sa = SaFirstForm({"phone": "0501234567"})
    assert local_sa.is_valid()
    assert local_sa.cleaned_data["phone"] == "+966501234567"

    # Contradictory default_region outside regions falls back to allowed regions.
    class RestrictedForm(forms.Form):
        phone = PhoneNumberField(default_region="SA", regions=("EG",))

    local_eg = RestrictedForm({"phone": "01012345678"})
    assert local_eg.is_valid()
    assert local_eg.cleaned_data["phone"] == "+201012345678"

    # Rejects landline and disallowed region with translated Arabic errors.
    with override_language("ar"):
        landline_form = GulfMobileForm({"phone": "+971 4 123 4567"})
        assert not landline_form.is_valid()
        assert landline_form.errors["phone"] == ["أدخل رقم هاتف جوال صحيحًا."]

        eg_form = GulfMobileForm({"phone": "+20 10 1234 5678"})
        assert not eg_form.is_valid()
        assert eg_form.errors["phone"] == ["أرقام الهاتف من هذه المنطقة غير مسموح بها."]

        bad_form = GulfMobileForm({"phone": "abc"})
        assert not bad_form.is_valid()
        assert bad_form.errors["phone"] == ["أدخل رقم هاتف صحيحًا."]


def test_phone_number_field_required_and_optional():
    class OptionalForm(forms.Form):
        phone = PhoneNumberField(required=False)

    empty_ok = OptionalForm({"phone": ""})
    assert empty_ok.is_valid()
    assert empty_ok.cleaned_data["phone"] == ""

    class RequiredForm(forms.Form):
        phone = PhoneNumberField(required=True)

    empty_bad = RequiredForm({"phone": ""})
    assert not empty_bad.is_valid()


# ---------------------------------------------------------------------------
# |phone_display template filter and format_phone_display helper
# ---------------------------------------------------------------------------

DISPLAY_CASES = [
    ("+966501234567", "+966 50 123 4567"),
    ("+966112345678", "+966 11 234 5678"),
    ("+971501234567", "+971 50 123 4567"),
    ("+97141234567", "+971 4 123 4567"),
    ("+96551234567", "+965 5123 4567"),
    ("+96522401234", "+965 2240 1234"),
    ("+97455123456", "+974 5512 3456"),
    ("+97444123456", "+974 4412 3456"),
    ("+97339123456", "+973 3912 3456"),
    ("+97317123456", "+973 1712 3456"),
    ("+96892123456", "+968 9212 3456"),
    ("+96824123456", "+968 2412 3456"),
    ("+201012345678", "+20 10 1234 5678"),
    ("+20223456789", "+20 2 2345 6789"),
    ("+2034567890", "+20 3 456 7890"),
    ("+20502345678", "+20 50 234 5678"),
    ("+962791234567", "+962 79 123 4567"),
    ("+96265123456", "+962 6 512 3456"),
]


@pytest.mark.parametrize(("e164", "expected_grouped"), DISPLAY_CASES)
def test_phone_display_filter_in_rendered_template(e164, expected_grouped):
    template = Template("{% load rtl_admin %}اتصل على {{ phone|phone_display }} الآن")
    rendered = template.render(Context({"phone": e164}))
    assert rendered == f"اتصل على {LRI}{expected_grouped}{PDI} الآن"
    assert format_phone_display(e164) == f"{LRI}{expected_grouped}{PDI}"


def test_phone_display_filter_region_argument_and_edge_cases():
    template = Template('{% load rtl_admin %}{{ phone|phone_display:"SA" }}')
    assert template.render(Context({"phone": "٠٥٠ ١٢٣ ٤٥٦٧"})) == f"{LRI}+966 50 123 4567{PDI}"

    empty_tpl = Template("{% load rtl_admin %}{{ phone|phone_display }}")
    assert empty_tpl.render(Context({"phone": None})) == ""
    assert empty_tpl.render(Context({"phone": ""})) == ""
    assert empty_tpl.render(Context({"phone": "   "})) == ""
    assert format_phone_display(None) == ""
    assert format_phone_display("   ") == ""

    # Escapes untrusted fallback HTML and preserves SafeString / autoescape off.
    xss = empty_tpl.render(Context({"phone": "<script>alert(1)</script>"}))
    assert xss == f"{LRI}&lt;script&gt;alert(1)&lt;/script&gt;{PDI}"

    safe = empty_tpl.render(Context({"phone": mark_safe("<b>raw</b>")}))
    assert safe == f"{LRI}<b>raw</b>{PDI}"

    no_escape = Template(
        "{% load rtl_admin %}{% autoescape off %}{{ phone|phone_display }}{% endautoescape %}"
    ).render(Context({"phone": "<b>raw</b>"}))
    assert no_escape == f"{LRI}<b>raw</b>{PDI}"

    # Non-string unrecognized value falls back cleanly.
    assert format_phone_display(12345) == f"{LRI}12345{PDI}"


def test_public_exports_from_package_root():
    for name in ("normalize_phone", "validate_phone", "format_phone_display", "PhoneNumberField"):
        assert name in django_rtl_admin.__all__
        assert getattr(django_rtl_admin, name) is getattr(phones_module, name)
