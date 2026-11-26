---
title: Python API | django-rtl-admin
description: Use Python helpers for numeric input normalization, bidi isolation, digit transliteration, and locale-aware numbers, currencies, percentages, dates, and times.
---

# Python API

Use the isolation and formatting helpers in display methods or custom templates.
They can read Django's active language and the [configuration](configuration.md).
For incoming form data, use `normalize_numeric_input` instead, and use
`arabic_search_regex` when building Arabic-tolerant `iregex` queries. None of
these helpers changes stored model values.

## Normalizing numeric input

`normalize_numeric_input(value, *, decimal_separator=".")` returns non-strings
unchanged. For strings it:

- Converts Arabic-Indic (`٠١٢٣٤٥٦٧٨٩`) and Persian (`۰۱۲۳۴۵۶۷۸۹`) digits to `0`–`9`.
- Replaces the Arabic decimal separator `٫` (U+066B) with `decimal_separator`
  and the minus sign `−` (U+2212) with ASCII `-`.
- Removes the Arabic thousands separator `٬` (U+066C). Inside the text it also
  removes nonbreaking space (U+00A0), narrow nonbreaking space (U+202F), and
  thin space (U+2009), but only when the space is directly between two digits.
- Strips Unicode `Bidi_Control` characters and trims surrounding whitespace.

```python
from django_rtl_admin import normalize_numeric_input

assert normalize_numeric_input("−١٬٢٣٤٫٥٠") == "-1234.50"
assert normalize_numeric_input("۱۲٫۵", decimal_separator=",") == "12,5"
assert normalize_numeric_input("١٢,٣ USD") == "12,3 USD"
```

The helper neither parses nor validates a number: it leaves letters and all
other punctuation alone. In particular, it does not guess whether an ASCII
comma is a decimal or grouping separator. The [admin mixin](admin-mixin.md#numeric-and-date-input)
uses it before Django parses a field, supplying Django's active decimal
separator for localized numeric fields.

## Arabic search folding

`arabic_search_regex(term)` turns a plain search term into a portable regular
expression that matches equivalent Arabic letter forms, diacritics, tatweel, and
digits across SQLite, PostgreSQL, and MySQL 8:

- Strips harakat (U+064B–U+065F, U+0670), tatweel (`ـ`, U+0640), and Unicode
  `Bidi_Control` characters from `term`.
- Folds alef variants (`آ`/`أ`/`إ`/`ا`/`ٱ`), teh marbuta and heh (`ة`/`ه`), alef
  maksura, yeh, Persian yeh, and yeh with hamza (`ئ`/`ى`/`ي`/`ی`), Arabic and
  Persian kaf (`ك`/`ک`), waw and waw with hamza (`ؤ`/`و`), and each digit across
  ASCII (`0`–`9`), Arabic-Indic (`٠`–`٩`), and Persian (`۰`–`۹`) into bracket
  character classes.
- Follows every Arabic letter with `[\u0640\u064b-\u065f\u0670]*` so stored
  harakat and tatweel never prevent a match.
- Wraps punctuation and symbol characters in single-character bracket classes
  and emits only literals, bracket classes, and `*`.

```python
import re

from django_rtl_admin import arabic_search_regex

pattern = arabic_search_regex("احمد ١٤٤٦")
assert re.fullmatch(pattern, "أَحْمَدُ 1446")
```

The [admin mixin](admin-mixin.md#arabic-search-folding) uses this helper in
`get_search_results()` for terms containing an Arabic letter or an Arabic-Indic
or Persian digit.

## Choosing an isolation helper

- `isolate()` strips any existing Unicode `Bidi_Control` characters and wraps an
  entire plain-text value; use `direction="ltr"` for an opaque identifier such
  as an ISBN.
- `isolate_runs()` strips existing Unicode `Bidi_Control` characters and isolates
  opposite-direction fragments inside plain-text prose.
- `mark_isolated()` and `mark_isolated_runs()` are the HTML-producing variants.
  Keep `autoescape=True` for untrusted text. `mark_isolated()` strips existing
  `Bidi_Control` characters when wrapping; already-safe HTML is not re-escaped,
  and `mark_isolated_runs()` leaves already-safe HTML untouched to avoid
  damaging markup.
- `strip_isolates()` removes all twelve Unicode `Bidi_Control` characters
  (`ALM`, `LRM`, `RLM`, `LRE`, `RLE`, `PDF`, `LRO`, `RLO`, `LRI`, `RLI`, `FSI`,
  and `PDI`). It does not strip HTML or non-bidi control characters.

```python
from django.utils import translation

from django_rtl_admin.bidi import isolate, mark_isolated_runs
from django_rtl_admin.formatting import format_number

reference = isolate("978-0-13-468599-1", direction="ltr")
with translation.override("ar-eg"):
    description = mark_isolated_runs("الإصدار v1.2.3")
    amount = format_number(1234.5, decimal_pos=2)
```

Isolation inserts Unicode characters, not HTML elements. Apply it when rendering,
not before saving business identifiers; the controls can survive copy/paste.

::: django_rtl_admin.bidi
    options:
      heading_level: 2
      members:
        - rtl_languages
        - is_rtl_language
        - current_direction
        - text_direction
        - has_mixed_direction
        - isolate
        - is_isolated
        - strip_isolates
        - mark_isolated
        - isolate_runs
        - mark_isolated_runs

## Locale-aware formatting

Install `django-rtl-admin[babel]` for CLDR separators and currency/date patterns.
Without Babel, or with `USE_BABEL=False`, number formatting renders from a
built-in CLDR table — the locale's own group and decimal separators, grouping
convention and digits — matching Babel's output for the supported locales, and
only locales the table does not cover fall back to Django plus digit
transliteration; date/time formatting still uses Django. An explicit `language`
is respected on every path.

Use `short`, `medium`, `long`, or `full` for portable date/datetime requests.
The Django fallback looks up patterns in the requested language's locale format
modules. Project modules in `FORMAT_MODULE_PATH` take precedence over Django's
built-in modules. For dates and datetimes, `short` selects the short format;
`medium`, `long`, and `full` select the regular format. If the locale does not
define `DATETIME_FORMAT`, the fallback combines `DATE_FORMAT` with `TIME_FORMAT`.
If it lacks `SHORT_DATETIME_FORMAT`, it combines `SHORT_DATE_FORMAT` with
`TIME_FORMAT` instead. Built-in CLDR patterns fill the gaps for Urdu (`ur`) and,
where Django has no Uyghur format module (4.2), Uyghur (`ug`). If neither the
locale modules nor the table cover a language, Django's defaults still apply.

On the Django fallback, `format_time()` uses the locale's `TIME_FORMAT` for
all four named styles. To request a specific layout, pass a Django format
string as `fmt`, such as `H:i:s` for hours, minutes, and seconds. Babel still
uses its own named styles and CLDR patterns for dates and times; digit
transliteration is unchanged on both paths.

When `USE_TZ=True`, `format_datetime()` and `format_time()` convert aware
`datetime` values to Django's active time zone with `django.utils.timezone.localtime()`
on both the Babel and Django fallback paths (and the `l10n_datetime` and
`l10n_time` template filters declare `expects_localtime=True`, respecting
`{% localtime off %}`); naive `datetime`/`time` values and plain `date` values
are left untouched.

`NUMERALS` controls digit shapes, not every separator. `transliterate_digits()`
converts digits among `latn`, `arab`, and `arabext` without changing punctuation.
Formatting helpers return text; apply isolation separately when needed.

`format_timedelta()` formats a `timedelta` or a number of seconds with CLDR unit
patterns; without Babel it uses Django's translated `timesince` strings. Its
`granularity`, `threshold`, `add_direction`, and `format` arguments mirror
`babel.dates.format_timedelta`. `format_filesize()` formats a byte count, using
powers of 1000 by default and powers of 1024 with `binary=True`; Django's
translated unit names are used on both backends.

::: django_rtl_admin.formatting
    options:
      heading_level: 2
      members:
        - arabic_search_regex
        - numbering_system
        - normalize_numeric_input
        - transliterate_digits
        - format_number
        - format_currency
        - format_percent
        - format_timedelta
        - format_filesize
        - format_date
        - format_datetime
        - format_time
