"""Arabic ordinal words, short ordinals, their template filters and the changelist column."""

from __future__ import annotations

import decimal
import enum
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.contrib import admin
from django.template import Context, Template
from django.test import RequestFactory, override_settings
from django.utils import translation
from django.utils.safestring import SafeString, mark_safe
from django.utils.translation import gettext_lazy

import django_rtl_admin
from django_rtl_admin import (
    BidiSafeAdminMixin,
    numbering_system,
    ordinal_display,
    ordinal_short,
    ordinal_words,
    transliterate_digits,
)
from django_rtl_admin import ordinals as ordinals_module
from django_rtl_admin.bidi import FSI, PDI
from django_rtl_admin.conf import rtl_settings
from django_rtl_admin.ordinals import ARABIC_SHORT_ORDINAL_MARKER, MAX_ORDINAL_WORDS
from django_rtl_admin.templatetags import rtl_admin as tags

from .testapp.admin import ChapterAdmin
from .testapp.models import Book, Category, Chapter

DOCS = Path(__file__).resolve().parents[1] / "docs"
TABLE = Path(__file__).parent / "data" / "arabic_ordinals.tsv"
COLUMNS = (
    ("masculine_definite", "masculine", True),
    ("feminine_definite", "feminine", True),
    ("masculine_indefinite", "masculine", False),
    ("feminine_indefinite", "feminine", False),
)
FORMS = [(gender, definite) for _, gender, definite in COLUMNS]
AR = {"accept-language": "ar"}
CHAPTERS_URL = "/admin/testapp/chapter/"


def load_table():
    header, *rows = (
        line.split("\t") for line in TABLE.read_text(encoding="utf-8").splitlines() if line
    )
    assert header == ["value", *(name for name, _, _ in COLUMNS)]
    return [dict(zip(header, row, strict=True)) for row in rows]


ROWS = load_table()
TABLE_CASES = [
    pytest.param(
        int(row["value"]),
        gender,
        definite,
        row[column],
        id=f"{row['value']}-{column}",
    )
    for row in ROWS
    for column, gender, definite in COLUMNS
]


def render(template, **context):
    return Template("{% load rtl_admin %}" + template).render(Context(context))


# ---------------------------------------------------------------------------
# 1 to 100 against the checked-in table
# ---------------------------------------------------------------------------


def test_the_table_lists_every_value_from_1_to_100_once():
    assert [int(row["value"]) for row in ROWS] == list(range(1, 101))
    assert len(TABLE_CASES) == 400
    for row in ROWS:
        for cell in row.values():
            assert cell and cell == cell.strip()


def test_the_table_follows_the_rules_of_arabic_ordinals():
    """Cross-check the reference table itself, independently of the module."""
    for row in ROWS:
        value = int(row["value"])
        masculine, feminine = row["masculine_definite"], row["feminine_definite"]
        # The indefinite form is the definite one without its articles, apart
        # from the two defective masculine words.
        assert masculine.startswith("ال") and feminine.startswith("ال")
        assert row["feminine_indefinite"] == re.sub(r"(^|\sو?)ال", r"\1", feminine)
        bare = re.sub(r"(^|\sو?)ال", r"\1", masculine)
        if value < 100 and (value == 2 or (value > 20 and value % 10 in (1, 2))):
            bare = bare.replace("ثاني", "ثانٍ").replace("حادي", "حادٍ")
        assert row["masculine_indefinite"] == bare
        # The tens and the hundred have a single form; everything else agrees
        # in gender.
        assert (masculine == feminine) is (value >= 20 and value % 10 == 0)
        if 11 <= value <= 19:
            assert masculine.endswith(" عشر") and feminine.endswith(" عشرة")
        if value > 20 and value % 10:
            units, tens = masculine.split(" و")
            assert tens == ROWS[value - value % 10 - 1]["masculine_definite"]
            assert units == ("الحادي" if value % 10 == 1 else ROWS[value % 10 - 1][COLUMNS[0][0]])


@pytest.mark.parametrize(("value", "gender", "definite", "expected"), TABLE_CASES)
def test_ordinal_words_1_to_100(value, gender, definite, expected):
    assert ordinal_words(value, gender=gender, definite=definite) == expected


def test_defaults_are_masculine_and_definite():
    for row in ROWS:
        assert ordinal_words(int(row["value"])) == row["masculine_definite"]


@pytest.mark.parametrize(
    ("value", "masculine", "feminine"),
    [
        (1, "الأول", "الأولى"),
        (2, "الثاني", "الثانية"),
        (11, "الحادي عشر", "الحادية عشرة"),
        (12, "الثاني عشر", "الثانية عشرة"),
        (19, "التاسع عشر", "التاسعة عشرة"),
        (20, "العشرون", "العشرون"),
        (21, "الحادي والعشرون", "الحادية والعشرون"),
        (99, "التاسع والتسعون", "التاسعة والتسعون"),
        (100, "المئة", "المئة"),
    ],
)
def test_the_special_forms_spelled_out(value, masculine, feminine):
    assert ordinal_words(value) == masculine
    assert ordinal_words(value, gender="feminine") == feminine


def test_indefinite_defective_forms_carry_their_tanwin():
    assert ordinal_words(2, definite=False) == "ثان\u064d"
    assert ordinal_words(21, definite=False) == "حاد\u064d وعشرون"
    assert ordinal_words(92, definite=False) == "ثان\u064d وتسعون"
    # 11 to 19 are invariable compounds: the ya stays.
    assert ordinal_words(11, definite=False) == "حادي عشر"
    assert ordinal_words(12, definite=False) == "ثاني عشر"
    assert ordinal_words(2, gender="feminine", definite=False) == "ثانية"


@pytest.mark.parametrize(
    ("gender", "expected"),
    [
        ("masculine", "الثالث"),
        ("m", "الثالث"),
        ("M", "الثالث"),
        ("feminine", "الثالثة"),
        ("f", "الثالثة"),
        (" Feminine ", "الثالثة"),
    ],
)
def test_gender_spellings(gender, expected):
    assert ordinal_words(3, gender=gender) == expected


@pytest.mark.parametrize("gender", ["", "x", "female", "fem", None, 1, True, b"f"])
def test_unknown_gender_raises_value_error(gender):
    with pytest.raises(ValueError, match="gender must be 'masculine' or 'feminine'") as excinfo:
        ordinal_words(3, gender=gender)
    assert repr(gender) in str(excinfo.value)


def test_definite_is_read_as_a_truth_value():
    assert ordinal_words(4, definite=0) == "رابع"
    assert ordinal_words(4, definite=1) == "الرابع"


# ---------------------------------------------------------------------------
# Above 100
# ---------------------------------------------------------------------------

ABOVE_100 = [
    # The cardinal of the hundreds and above, then waw and the ordinal of the
    # last two digits.
    (101, "masculine", True, "المئة والأول"),
    (101, "feminine", True, "المئة والأولى"),
    (101, "masculine", False, "مئة وأول"),
    (101, "feminine", False, "مئة وأولى"),
    (102, "masculine", False, "مئة وثانٍ"),
    (110, "feminine", True, "المئة والعاشرة"),
    (111, "masculine", True, "المئة والحادي عشر"),
    (111, "feminine", True, "المئة والحادية عشرة"),
    (112, "feminine", False, "مئة وثانية عشرة"),
    (120, "masculine", True, "المئة والعشرون"),
    (121, "masculine", True, "المئة والحادي والعشرون"),
    (121, "masculine", False, "مئة وحادٍ وعشرون"),
    (125, "masculine", True, "المئة والخامس والعشرون"),
    (125, "feminine", True, "المئة والخامسة والعشرون"),
    (125, "feminine", False, "مئة وخامسة وعشرون"),
    (199, "feminine", True, "المئة والتاسعة والتسعون"),
    # Round hundreds and thousands are their own cardinal word.
    (200, "masculine", True, "المئتان"),
    (200, "feminine", False, "مئتان"),
    (201, "feminine", True, "المئتان والأولى"),
    (300, "masculine", True, "الثلاثمئة"),
    (400, "masculine", False, "أربعمئة"),
    (512, "masculine", True, "الخمسمئة والثاني عشر"),
    (600, "masculine", True, "الستمئة"),
    (700, "masculine", True, "السبعمئة"),
    (800, "masculine", True, "الثمانمئة"),
    (999, "feminine", True, "التسعمئة والتاسعة والتسعون"),
    (1000, "masculine", True, "الألف"),
    (1000, "feminine", False, "ألف"),
    (1001, "feminine", True, "الألف والأولى"),
    (1100, "masculine", True, "الألف والمئة"),
    (1234, "masculine", True, "الألف والمئتان والرابع والثلاثون"),
    (1234, "masculine", False, "ألف ومئتان ورابع وثلاثون"),
    (2000, "masculine", True, "الألفان"),
    (2024, "feminine", True, "الألفان والرابعة والعشرون"),
    # The counted noun: plural after 3 to 10, accusative singular after 11 to
    # 99, singular after a round hundred.
    (3000, "masculine", False, "ثلاثة آلاف"),
    (3000, "masculine", True, "ثلاثة الآلاف"),
    (3005, "feminine", False, "ثلاثة آلاف وخامسة"),
    (10_000, "masculine", False, "عشرة آلاف"),
    (11_000, "masculine", False, "أحد عشر ألفًا"),
    (11_000, "masculine", True, "الأحد عشر ألفًا"),
    (12_345, "feminine", False, "اثنا عشر ألفًا وثلاثمئة وخامسة وأربعون"),
    (12_345, "feminine", True, "الاثنا عشر ألفًا والثلاثمئة والخامسة والأربعون"),
    (13_000, "masculine", False, "ثلاثة عشر ألفًا"),
    (20_000, "masculine", True, "العشرون ألفًا"),
    (21_000, "masculine", False, "واحد وعشرون ألفًا"),
    (22_000, "masculine", True, "الاثنان والعشرون ألفًا"),
    (99_000, "masculine", False, "تسعة وتسعون ألفًا"),
    (100_000, "masculine", False, "مئة ألف"),
    (100_000, "masculine", True, "مئة الألف"),
    (101_000, "masculine", False, "مئة ألف وألف"),
    (102_000, "masculine", False, "مئة ألف وألفان"),
    (103_000, "masculine", False, "مئة وثلاثة آلاف"),
    (111_000, "masculine", False, "مئة وأحد عشر ألفًا"),
    (125_000, "masculine", True, "المئة والخمسة والعشرون ألفًا"),
    (200_000, "masculine", False, "مئتا ألف"),
    (300_000, "masculine", False, "ثلاثمئة ألف"),
    (999_999, "masculine", False, "تسعمئة وتسعة وتسعون ألفًا وتسعمئة وتاسع وتسعون"),
    (1_000_000, "masculine", True, "المليون"),
    (2_000_000, "masculine", False, "مليونان"),
    (3_000_000, "masculine", False, "ثلاثة ملايين"),
    (11_000_000, "masculine", False, "أحد عشر مليونًا"),
    (1_001_001, "feminine", True, "المليون والألف والأولى"),
    (1_000_000_000, "masculine", True, "المليار"),
    (2_000_000_000, "masculine", False, "ملياران"),
    (5_000_000_000, "masculine", False, "خمسة مليارات"),
    (40_000_000_007, "feminine", False, "أربعون مليارًا وسابعة"),
]


@pytest.mark.parametrize(("value", "gender", "definite", "expected"), ABOVE_100)
def test_ordinal_words_above_100(value, gender, definite, expected):
    assert ordinal_words(value, gender=gender, definite=definite) == expected


@pytest.mark.parametrize(("gender", "definite"), FORMS)
def test_above_100_is_the_round_cardinal_then_the_ordinal_of_the_last_two_digits(gender, definite):
    for value in (*range(101, 1300), 4_321, 19_999, 250_075, 7_000_042, MAX_ORDINAL_WORDS):
        words = ordinal_words(value, gender=gender, definite=definite)
        assert "  " not in words and words == words.strip()
        last_two = value % 100
        if not last_two:
            # Neither gender nor an ordinal form applies to a round cardinal.
            assert words == ordinal_words(value, gender="masculine", definite=definite)
            continue
        leading = ordinal_words(value - last_two, gender=gender, definite=definite)
        ending = ordinal_words(last_two, gender=gender, definite=definite)
        assert words == f"{leading} و{ending}"


def test_the_largest_supported_value_and_the_first_one_past_it():
    assert MAX_ORDINAL_WORDS == 999_999_999_999
    assert ordinal_words(MAX_ORDINAL_WORDS).endswith("والتسعمئة والتاسع والتسعون")
    with pytest.raises(ValueError, match=r"up to 999,999,999,999.*ordinal_short\(\)"):
        ordinal_words(MAX_ORDINAL_WORDS + 1)
    assert ordinal_short(MAX_ORDINAL_WORDS + 1, language="en") == "1000000000000th"


# ---------------------------------------------------------------------------
# Accepted and rejected values
# ---------------------------------------------------------------------------


class Rank(enum.IntEnum):
    THIRD = 3


class Indexable:
    def __index__(self):
        return 3


@pytest.mark.parametrize("value", [3, "3", " 3 ", "+3", "003", "٣", "۳", Rank.THIRD, Indexable()])
def test_integers_and_integer_strings_are_accepted(value):
    assert ordinal_words(value) == "الثالث"
    assert ordinal_short(value, language="en") == "3rd"


INVALID_VALUES = [
    pytest.param(0, "starting at 1", id="zero"),
    pytest.param(-1, "starting at 1", id="negative"),
    pytest.param(-100, "starting at 1", id="negative-hundred"),
    pytest.param("0", "starting at 1", id="zero-string"),
    pytest.param("-5", "starting at 1", id="negative-string"),
    pytest.param("٠", "starting at 1", id="arabic-indic-zero"),
    pytest.param(True, "not the boolean True", id="true"),
    pytest.param(False, "not the boolean False", id="false"),
    pytest.param(1.0, "not the float 1.0", id="whole-float"),
    pytest.param(2.5, "not the float 2.5", id="float"),
    pytest.param(float("nan"), "not the float nan", id="nan"),
    pytest.param(float("inf"), "not the float inf", id="infinity"),
    pytest.param("", "not the non-integer string ''", id="empty-string"),
    pytest.param("   ", "not the non-integer string", id="blank-string"),
    pytest.param("abc", "not the non-integer string 'abc'", id="letters"),
    pytest.param("1.5", "not the non-integer string '1.5'", id="decimal-string"),
    pytest.param("3.0", "not the non-integer string '3.0'", id="whole-decimal-string"),
    pytest.param("١٫٥", "not the non-integer string", id="arabic-decimal-string"),
    pytest.param("3rd", "not the non-integer string '3rd'", id="suffixed-string"),
    pytest.param("1_000", "not the non-integer string '1_000'", id="underscored-string"),
    pytest.param("1e3", "not the non-integer string '1e3'", id="exponent-string"),
    pytest.param("الثالث", "not the non-integer string", id="words"),
    pytest.param(None, "not the NoneType None", id="none"),
    pytest.param(decimal.Decimal("3"), "not the Decimal", id="decimal"),
    pytest.param(b"3", "not the bytes b'3'", id="bytes"),
    pytest.param([3], "not the list", id="list"),
    pytest.param(3 + 0j, "not the complex", id="complex"),
]


@pytest.mark.parametrize("function", [ordinal_words, ordinal_short], ids=["words", "short"])
@pytest.mark.parametrize(("value", "message"), INVALID_VALUES)
def test_invalid_values_raise_value_error(function, value, message):
    with pytest.raises(ValueError, match="An ordinal needs a positive integer") as excinfo:
        function(value)
    assert message in str(excinfo.value)


# ---------------------------------------------------------------------------
# ordinal_short
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1, "1st"),
        (2, "2nd"),
        (3, "3rd"),
        (4, "4th"),
        (10, "10th"),
        (11, "11th"),
        (12, "12th"),
        (13, "13th"),
        (14, "14th"),
        (20, "20th"),
        (21, "21st"),
        (22, "22nd"),
        (23, "23rd"),
        (100, "100th"),
        (101, "101st"),
        (111, "111th"),
        (112, "112th"),
        (113, "113th"),
        (122, "122nd"),
        (1003, "1003rd"),
        (1011, "1011th"),
    ],
)
def test_english_short_ordinals(value, expected):
    assert ordinal_short(value, language="en") == expected
    assert ordinal_short(value, language="en-gb") == expected
    assert ordinal_short(value, language="en_US") == expected


def test_arabic_short_ordinal_is_the_article_and_a_tatweel_before_the_digits():
    assert ARABIC_SHORT_ORDINAL_MARKER == "\u0627\u0644\u0640"
    assert ordinal_short(1, language="ar") == "الـ1"
    assert ordinal_short(25, language="ar") == "الـ25"
    assert ordinal_short(1000, language="ar") == "الـ1000"
    assert ordinal_short("٢٥", language="ar") == "الـ25"


LOCALIZED = {"LOCALIZE_CHANGELIST_DIGITS": True}


def test_short_ordinal_digits_are_latin_while_digit_localization_is_off():
    """LOCALIZE_CHANGELIST_DIGITS is off by default, so no locale rewrites the digits."""
    assert rtl_settings.LOCALIZE_CHANGELIST_DIGITS is False
    for language in ("ar", "ar-eg", "ar_SA", "ar-ma"):
        assert ordinal_short(25, language=language) == "الـ25"
    assert ordinal_short(25, language="fa") == "25"
    assert ordinal_short(25, language="en") == "25th"
    with override_settings(RTL_ADMIN={"LOCALIZE_CHANGELIST_DIGITS": False, "NUMERALS": "arab"}):
        assert ordinal_short(25, language="ar-eg") == "الـ25"
        assert ordinal_short(25, language="en") == "25th"


def test_short_ordinal_digits_follow_the_locale_when_digit_localization_is_on():
    with override_settings(RTL_ADMIN=LOCALIZED):
        assert ordinal_short(25, language="ar-eg") == "الـ٢٥"
        assert ordinal_short(25, language="ar_SA") == "الـ٢٥"
        assert ordinal_short(25, language="ar-ma") == "الـ25"
        assert ordinal_short(25, language="ar") == "الـ25"
        assert ordinal_short("٢٥", language="ar-eg") == "الـ٢٥"
        for language in ("ar", "ar-eg", "ar-ae", "ar-sa"):
            digits = transliterate_digits("1234567890", numbering_system(language))
            assert ordinal_short(1234567890, language=language) == f"الـ{digits}"


@pytest.mark.parametrize("use_babel", [True, False])
@pytest.mark.parametrize(
    ("numerals", "language", "expected"),
    [
        ("arab", "ar", "الـ٢٥"),
        ("latn", "ar-eg", "الـ25"),
        ("arabext", "ar", "الـ۲۵"),
        ("auto", "ar-eg", "الـ٢٥"),
        ("auto", "ar", "الـ25"),
        ("auto", "en", "25th"),
        ("arab", "en", "٢٥th"),
    ],
)
def test_localized_short_ordinal_digits_honour_numerals(use_babel, numerals, language, expected):
    with override_settings(RTL_ADMIN={**LOCALIZED, "NUMERALS": numerals, "USE_BABEL": use_babel}):
        assert ordinal_short(25, language=language) == expected


def test_short_ordinal_reads_the_setting_from_conf_on_every_call():
    assert ordinals_module.rtl_settings is rtl_settings
    assert ordinal_short(3, language="ar-eg") == "الـ3"
    with override_settings(RTL_ADMIN=LOCALIZED):
        assert ordinal_short(3, language="ar-eg") == "الـ٣"
    assert ordinal_short(3, language="ar-eg") == "الـ3"


@pytest.mark.parametrize(
    ("language", "plain", "localized"),
    [("he", "3", "3"), ("fr", "3", "3"), ("fa", "3", "۳"), ("ps", "3", "۳"), ("ur", "3", "3")],
)
def test_other_languages_get_the_bare_digits(language, plain, localized):
    assert ordinal_short(3, language=language) == plain
    with override_settings(RTL_ADMIN=LOCALIZED):
        assert ordinal_short(3, language=language) == localized


def test_short_ordinal_follows_the_active_language():
    with translation.override("ar"):
        assert ordinal_short(3) == "الـ3"
    with translation.override("ar-eg"):
        assert ordinal_short(3) == "الـ3"
        assert ordinal_short(3, language="en") == "3rd"
        with override_settings(RTL_ADMIN=LOCALIZED):
            assert ordinal_short(3) == "الـ٣"
            assert ordinal_short(3, language="en") == "3rd"
    with translation.override("en"):
        assert ordinal_short(3) == "3rd"
        assert ordinal_short(3, language="ar") == "الـ3"
    with translation.override(None):
        assert ordinal_short(3) == "3rd"


# ---------------------------------------------------------------------------
# Template filters
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("language", ["ar", "en"])
@pytest.mark.parametrize(
    ("template", "expected"),
    [
        ("{{ n|ordinal_ar }}", "الثالث"),
        ('{{ n|ordinal_ar:"m" }}', "الثالث"),
        ('{{ n|ordinal_ar:"f" }}', "الثالثة"),
        ('{{ n|ordinal_ar:"f,indef" }}', "ثالثة"),
        ('{{ n|ordinal_ar:"indef,f" }}', "ثالثة"),
        ('{{ n|ordinal_ar:"indef" }}', "ثالث"),
        ('{{ n|ordinal_ar:"m,def" }}', "الثالث"),
        ('{{ n|ordinal_ar:"feminine,indefinite" }}', "ثالثة"),
        ('{{ n|ordinal_ar:"masculine,definite" }}', "الثالث"),
        ('{{ n|ordinal_ar:" F , INDEF " }}', "ثالثة"),
        ('{{ n|ordinal_ar:"" }}', "الثالث"),
        ("{{ n|ordinal_ar:options }}", "الثالثة"),
        ("{{ n|ordinal_ar:nothing }}", "الثالث"),
    ],
)
def test_ordinal_ar_filter_renders_arabic_words_in_both_languages(language, template, expected):
    with translation.override(language):
        assert render(template, n=3, options="f", nothing=None) == expected


@pytest.mark.parametrize(
    ("language", "expected", "localized"),
    [
        ("ar", "الـ3", "الـ3"),
        ("ar-eg", "الـ3", "الـ٣"),
        ("en", "3rd", "3rd"),
        ("he", "3", "3"),
        ("fa", "3", "۳"),
    ],
)
def test_ordinal_short_filter_follows_the_active_language(language, expected, localized):
    with translation.override(language):
        assert render("{{ n|ordinal_short }}", n=3) == expected
        assert render("{{ n|ordinal_short }}", n="3") == expected
        with override_settings(RTL_ADMIN=LOCALIZED):
            assert render("{{ n|ordinal_short }}", n=3) == localized
            assert render("{{ n|ordinal_short }}", n="٣") == localized


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        ("ar", "<p>الطابق الحادي والعشرون (الـ21) والفاتورة الثانية عشرة، طابق ثانٍ</p>"),
        ("en", "<p>الطابق الحادي والعشرون (21st) والفاتورة الثانية عشرة، طابق ثانٍ</p>"),
    ],
)
def test_both_filters_in_one_rendered_template(language, expected):
    template = (
        "<p>الطابق {{ floor|ordinal_ar }} ({{ floor|ordinal_short }}) "
        'والفاتورة {{ invoice|ordinal_ar:"f" }}، طابق {{ second|ordinal_ar:"m,indef" }}</p>'
    )
    with translation.override(language):
        assert render(template, floor=21, invoice=12, second=2) == expected


def test_filters_read_the_template_language_block():
    template = (
        "{% load i18n %}{% language 'ar-eg' %}{{ n|ordinal_short }}{% endlanguage %} "
        "{% language 'en' %}{{ n|ordinal_short }} {{ n|ordinal_ar }}{% endlanguage %}"
    )
    assert render(template, n=22) == "الـ22 22nd الثاني والعشرون"
    with override_settings(RTL_ADMIN=LOCALIZED):
        assert render(template, n=22) == "الـ٢٢ 22nd الثاني والعشرون"


@pytest.mark.parametrize("name", ["ordinal_ar", "ordinal_short"])
def test_filters_are_registered_as_safe(name):
    assert tags.register.filters[name].is_safe is True
    assert not getattr(tags.register.filters[name], "needs_autoescape", False)


@pytest.mark.parametrize("name", ["ordinal_ar", "ordinal_short"])
def test_filters_are_autoescape_safe(name):
    with translation.override("en"):
        valid = render(f"{{{{ n|{name} }}}}", n=7)
        assert valid in {"السابع", "7th"}
        # Nothing to escape in a real ordinal, with or without autoescaping...
        assert (
            render(f"{{% autoescape off %}}{{{{ n|{name} }}}}{{% endautoescape %}}", n=7) == valid
        )
        assert render(f"{{{{ n|{name} }}}}", n=mark_safe("7")) == valid
        # ...and a value that is not a number is escaped like any other variable.
        hostile = '<script>alert("x")</script>'
        escaped = "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;"
        assert render(f"{{{{ v|{name} }}}}", v=hostile) == escaped
        assert render(f"{{{{ v|{name}|upper }}}}", v="<b>") == "&lt;B&gt;"
        assert (
            render(f"{{% autoescape off %}}{{{{ v|{name} }}}}{{% endautoescape %}}", v=hostile)
            == hostile
        )
        # Markup the project already trusted is not escaped a second time.
        assert render(f"{{{{ v|{name} }}}}", v=mark_safe("<b>3</b>")) == "<b>3</b>"


def test_ordinal_ar_keeps_hostile_markup_escaped_with_an_argument():
    assert render('{{ v|ordinal_ar:"f,indef" }}', v="<i>2</i>") == "&lt;i&gt;2&lt;/i&gt;"
    assert render("{{ n|ordinal_ar:options }}", n=3, options="<b>") == "3"


def test_filter_output_stays_safe_for_a_safe_input_and_can_be_chained():
    assert render("{{ n|ordinal_ar|bidi_isolate }}", n=5) == f"{FSI}الخامس{PDI}"
    assert render('{{ n|ordinal_short|bidi_isolate:"ltr" }}', n=5) == "\u20665th\u2069"
    assert not isinstance(tags.ordinal_ar(5), SafeString)
    assert tags.ordinal_ar(5, "f") == "الخامسة"
    assert tags.ordinal_short("5") == "5th"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, ""),
        ("", ""),
        (0, "0"),
        (-3, "-3"),
        (True, "True"),
        (2.5, "2.5"),
        ("abc", "abc"),
        ("3rd", "3rd"),
        (decimal.Decimal("3"), "3"),
    ],
)
def test_filters_fail_silently_on_values_that_are_not_ordinals(value, expected):
    with translation.override("en"):
        assert render("{{ v|ordinal_ar }}", v=value) == expected
        assert render('{{ v|ordinal_ar:"f" }}', v=value) == expected
        assert render("{{ v|ordinal_short }}", v=value) == expected
        assert render("[{{ missing|ordinal_ar }}{{ missing|ordinal_short }}]") == "[]"


@pytest.mark.parametrize("options", ["x", "fem", "f,x", "indef,neuter", "f indef", 5])
def test_ordinal_ar_returns_the_value_unchanged_for_an_unknown_argument(options):
    assert render("{{ n|ordinal_ar:options }}", n=3, options=options) == "3"
    assert tags.ordinal_ar(3, options) == 3


def test_ordinal_ar_beyond_the_spelled_range_returns_the_number():
    assert render("{{ n|ordinal_ar }}", n=MAX_ORDINAL_WORDS + 1) == str(MAX_ORDINAL_WORDS + 1)
    assert render("{{ n|ordinal_ar }}", n=1500) == "الألف والخمسمئة"


# ---------------------------------------------------------------------------
# ordinal_display
# ---------------------------------------------------------------------------


def test_ordinal_display_carries_what_the_admin_reads():
    column = ordinal_display("number")
    assert callable(column)
    assert column.__name__ == "number"
    assert column.admin_order_field == "number"
    assert not hasattr(column, "short_description")
    assert not getattr(column, "boolean", False)

    label = gettext_lazy("Rank")
    described = ordinal_display("rank", gender="feminine", description=label)
    assert described.short_description is label
    assert described.admin_order_field == "rank"
    assert ordinal_display("book__price").admin_order_field == "book__price"
    # Each call returns its own callable, so two columns never share state.
    assert ordinal_display("number") is not column


def test_ordinal_display_spells_the_field_value():
    chapter = SimpleNamespace(number=3, book=SimpleNamespace(edition=21, publisher=None))
    assert ordinal_display("number")(chapter) == "الثالث"
    assert ordinal_display("number", "f")(chapter) == "الثالثة"
    assert ordinal_display("number", gender="feminine")(chapter) == "الثالثة"
    assert ordinal_display("number", definite=False)(chapter) == "ثالث"
    assert ordinal_display("number", "f", definite=False)(chapter) == "ثالثة"
    assert ordinal_display("book__edition", "f")(chapter) == "الحادية والعشرون"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        (0, "0"),
        (-2, "-2"),
        (2.5, "2.5"),
        ("n/a", "n/a"),
        ("٧", "السابع"),
        (MAX_ORDINAL_WORDS + 1, "1000000000000"),
    ],
)
def test_ordinal_display_never_raises_for_a_stored_value(value, expected):
    assert ordinal_display("number")(SimpleNamespace(number=value)) == expected


def test_ordinal_display_returns_none_when_the_path_ends_early():
    chapter = SimpleNamespace(number=3, book=None)
    assert ordinal_display("book__edition")(chapter) is None
    assert ordinal_display("missing")(chapter) is None


@pytest.mark.parametrize("field_name", ["", "  ", None, 3])
def test_ordinal_display_requires_a_field_name(field_name):
    with pytest.raises(ValueError, match="needs a field name"):
        ordinal_display(field_name)


def test_ordinal_display_rejects_an_unknown_gender_when_it_is_built():
    with pytest.raises(ValueError, match="gender must be 'masculine' or 'feminine'"):
        ordinal_display("number", gender="neuter")


def test_registered_admin_passes_the_system_checks():
    model_admin = admin.site._registry[Chapter]
    assert isinstance(model_admin, ChapterAdmin)
    assert model_admin.check() == []


def cells(html, name="number"):
    return re.findall(rf'<td class="field-{name}">(.*?)</td>', html)


@pytest.fixture
def chapters(db):
    book = Book.objects.create(title="مقدمة ابن خلدون", isbn="978-9953-0-0001-1")
    numbers = (2, 100, 1, 21, 125, 11)
    return [
        Chapter.objects.create(book=book, number=number, title=f"فصل {number}")
        for number in numbers
    ]


@pytest.mark.django_db
def test_changelist_shows_arabic_ordinals_and_keeps_the_column_sortable(admin_client, chapters):
    response = admin_client.get(CHAPTERS_URL, headers=AR)
    html = response.content.decode()
    assert response.status_code == 200
    assert '<html lang="ar" dir="rtl"' in html
    # Chapter.Meta.ordering is ("number",).
    assert cells(html) == [
        "الأول",
        "الثاني",
        "الحادي عشر",
        "الحادي والعشرون",
        "المئة",
        "المئة والخامس والعشرون",
    ]
    header = re.search(r'<th scope="col" class="([^"]*column-number[^"]*)">(.*?)</th>', html, re.S)
    assert header is not None
    # The admin recognises the column as the one Meta.ordering sorts by.
    assert header[1].split() == ["sortable", "column-number", "sorted", "ascending"]
    assert re.search(r'<a [^>]*href="\?o=-2"[^>]*>Number</a>', header[2])
    cl = response.context["cl"]
    assert cl.get_ordering_field(cl.list_display[-1]) == "number"
    assert dict(cl.get_ordering_field_columns()) == {2: "asc"}


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("order", "numbers"),
    [("2", [1, 2, 11, 21, 100, 125]), ("-2", [125, 100, 21, 11, 2, 1])],
)
def test_changelist_sorts_the_ordinal_column_by_the_number(admin_client, chapters, order, numbers):
    response = admin_client.get(CHAPTERS_URL, {"o": order}, headers=AR)
    assert [chapter.number for chapter in response.context["cl"].result_list] == numbers
    assert cells(response.content.decode()) == [ordinal_words(number) for number in numbers]
    assert ("sorted ascending" if order == "2" else "sorted descending") in (
        response.content.decode()
    )


@pytest.mark.django_db
def test_changelist_words_stay_arabic_in_an_english_interface(admin_client, chapters):
    html = admin_client.get(CHAPTERS_URL).content.decode()
    assert '<html lang="en" dir="ltr"' in html
    assert cells(html)[:2] == ["الأول", "الثاني"]


@pytest.mark.django_db
@pytest.mark.parametrize("bases", [(admin.ModelAdmin,), (BidiSafeAdminMixin, admin.ModelAdmin)])
def test_ordinal_display_in_an_admin_with_and_without_the_mixin(admin_user, chapters, bases):
    Chapter.objects.create(book=chapters[0].book, number=0, title="تمهيد")
    column = ordinal_display("number", "f", definite=False, description="الترتيب")
    model_admin = type("OrdinalChapterAdmin", bases, {"list_display": ("title", column)})(
        Chapter, admin.site
    )
    assert model_admin.check() == []
    request = RequestFactory().get(CHAPTERS_URL, {"o": "-2"})
    request.user = admin_user
    with translation.override("ar"):
        assert model_admin.get_list_display(request)[-1] is column
        response = model_admin.changelist_view(request)
        response.render()
    html = response.content.decode()
    assert cells(html) == [
        "مئة وخامسة وعشرون",
        "مئة",
        "حادية وعشرون",
        "حادية عشرة",
        "ثانية",
        "أولى",
        "0",
    ]
    assert re.search(r'class="sortable column-number sorted descending">.*?الترتيب', html, re.S)


@pytest.mark.django_db
def test_ordinal_display_follows_a_relation_and_renders_an_empty_value(admin_user):
    category = Category.objects.create(name="تاريخ")
    Book.objects.create(title="أ", isbn="1", category=category)
    Book.objects.create(title="ب", isbn="2")
    column = ordinal_display("category__pk", description="التصنيف")
    model_admin = type(
        "OrdinalBookAdmin",
        (BidiSafeAdminMixin, admin.ModelAdmin),
        {"list_display": ("title", column)},
    )(Book, admin.site)
    request = RequestFactory().get("/admin/testapp/book/")
    request.user = admin_user
    with translation.override("ar"):
        response = model_admin.changelist_view(request)
        response.render()
    assert cells(response.content.decode(), "category__pk") == [
        ordinal_words(category.pk),
        model_admin.get_empty_value_display(),
    ]


# ---------------------------------------------------------------------------
# Public API and documentation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["ordinal_words", "ordinal_short", "ordinal_display"])
def test_the_helpers_are_exported_from_the_package_root(name):
    assert name in django_rtl_admin.__all__
    assert getattr(django_rtl_admin, name) is getattr(ordinals_module, name)


@pytest.mark.parametrize("page", ["api.md", "api.ar.md"])
def test_the_documented_examples_hold(page):
    text = (DOCS / page).read_text(encoding="utf-8")
    section = text.split("{ #arabic-ordinals }", 1)[1].split("\n## ", 1)[0]
    blocks = re.findall(r"```python\n(.*?)```", section, re.S)
    assert blocks
    with translation.override("en"):
        for block in blocks:
            exec(compile(block, page, "exec"), {})
