---
title: Python API | django-rtl-admin
description: Use Python and ORM helpers for Arabic sorting, search, and slugs, numeric input normalization, bidi isolation, digit transliteration, and locale-aware formatting.
---

# Python API

Use the isolation and formatting helpers in display methods or custom templates.
They can read Django's active language and the [configuration](configuration.md).
For incoming form data, use `normalize_numeric_input`; for Arabic-tolerant
`iregex` queries, use `arabic_search_regex`; and for slugs from Arabic-script
text, use `arabic_slugify`. These helpers return values without saving them.

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

## `arabic_slugify` { #arabic-slugify }

`arabic_slugify(value, *, allow_unicode=False, max_length=None)` makes a slug
from Arabic-script text. In both modes it removes Arabic diacritics
(U+064B–U+065F and U+0670), tatweel (`ـ`, U+0640), and Unicode `Bidi_Control`
characters, and converts Arabic-Indic and Persian digits to ASCII.

- With `allow_unicode=True`, Django's Unicode `slugify()` runs on the cleaned
  text and can keep Arabic-script letters.
- In the default ASCII mode, compatibility normalization handles Arabic
  presentation forms. The helper transliterates the letters below before
  applying Django's ASCII `slugify()`. This is a fixed letter-by-letter mapping,
  not phonetic romanization. If the input contains Arabic characters but no
  ASCII slug survives, the result falls back to `arabic`.

| Letters | ASCII | Letters | ASCII | Letters | ASCII |
| --- | --- | --- | --- | --- | --- |
| `ا أ إ آ ٱ ء ع ى` | `a` | `ز` | `z` | `ق` | `q` |
| `ب` | `b` | `س ص` | `s` | `ك ک` | `k` |
| `ت ط` | `t` | `ش` | `sh` | `ل` | `l` |
| `ث` | `th` | `ظ` | `z` | `م` | `m` |
| `ج` | `j` | `غ` | `gh` | `ن` | `n` |
| `ح ه ة ہ ۀ ە` | `h` | `ف` | `f` | `و ؤ` | `w` |
| `خ` | `kh` | `پ` | `p` | `ي ی ئ` | `y` |
| `د ض` | `d` | `چ` | `ch` | `گ` | `g` |
| `ذ` | `dh` | `ژ` | `zh` | `ر` | `r` |

If the slug exceeds `max_length`, it is cut at the last hyphen at or before
that limit, omitting the hyphen itself. If the first segment is too long,
it is cut to the limit. `None` means no limit; zero or a negative limit returns
an empty string.

```python
from django_rtl_admin import arabic_slugify

assert arabic_slugify("مُقَدِّمَة ١٢") == "mqdmh-12"
assert arabic_slugify("مُقَدِّمَة ١٢", allow_unicode=True) == "مقدمة-12"
assert arabic_slugify("پژوهش ۱۴۰۳") == "pzhwhsh-1403"
assert arabic_slugify("مقدمة الكتاب", max_length=9) == "mqdmh"
assert arabic_slugify("مقدمة الكتاب", max_length=3) == "mqd"
```

This helper does not check uniqueness. See [Arabic slug prepopulation](admin-mixin.md#arabic-slug-prepopulation)
for admin integration and validation behavior.

::: django_rtl_admin.arabic_slugify
    options:
      heading_level: 3
      show_root_full_path: false

## Arabic sort keys

Use `arabic_sort_key(value)` as the `key` for Python's `sorted()`. It returns a
lowercase string, or the empty string (`""`) for `None`. It strips harakat
(U+064B–U+065F and U+0670), tatweel (`ـ`), and Unicode `Bidi_Control` characters.
It maps `آ`, `أ`, `إ`, and `ٱ` to `ا`; `ة` to `ه`; `ى` and `ئ` to `ي`; and
`ؤ` to `و`. Arabic-Indic and Persian digits become ASCII digits. The result is a text
key, not a numeric value or a replacement for the original spelling.

```python
from django_rtl_admin import arabic_sort_key

assert arabic_sort_key("مَكْتَبَة ١٢") == arabic_sort_key("مكتبه ۱۲") == "مكتبه 12"
assert arabic_sort_key(None) == ""
titles = ["آفاق العلم", "أبواب المدينة", "إدارة الوقت"]
assert sorted(titles, key=arabic_sort_key) == ["أبواب المدينة", "إدارة الوقت", "آفاق العلم"]
```

For a queryset, `arabic_sort_expression(field_name)` builds a Django ORM
expression that applies the same substitutions with `Replace` and lowercases
the result with `Lower`. For example, given a `Book` model with a text field
`title_ar`:

```python
from django_rtl_admin import arabic_sort_expression

by_title = arabic_sort_expression("title_ar")
ascending = Book.objects.order_by(by_title.asc(), "pk")
descending = Book.objects.order_by(by_title.desc(), "pk")
```

PostgreSQL and MySQL 8 use nested `REPLACE` calls followed by `LOWER`. SQLite
uses a scalar `WITH` subquery to avoid the parser stack limit on older versions:
shorter chains of `REPLACE` calls pass their results to the next stage, and the
final `SELECT` applies `LOWER`.

No custom collation is installed. The query computes the key for each row, so a
normal index on the title may not speed up this sort. The secondary `pk` gives
tied titles a predictable order.
The database still supplies the collation, case conversion, and `NULL` placement:
unlike the Python helper, the expression leaves `NULL` as `NULL`. Don't assume
identical ordering across backends or a full locale-specific dictionary sort.
Neither helper needs the [admin mixin](admin-mixin.md#arabic-changelist-ordering)
or changes the stored text.

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
The [admin mixin](admin-mixin.md#changelist-digit-localization) calls
`transliterate_digits(text, numbering_system())` on eligible numeric and temporal
changelist cells when `LOCALIZE_CHANGELIST_DIGITS` or `bidi_local_digits` is
enabled, preserving Django's rendered separators. Formatting helpers return text;
apply isolation separately when needed.

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
        - arabic_sort_key
        - arabic_sort_expression
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
        - format_hijri_date

## Hijri dates { #hijri-dates }

Saudi and Gulf admins usually need the Umm al-Qura calendar, which Babel does
not provide. `to_hijri()` and `from_hijri()` convert between Gregorian dates
and the official Umm al-Qura table for 1343–1500 AH (1 August 1924 to
16 November 2077 CE) without adding a runtime dependency. Dates outside that
range raise `ValueError`; `to_hijri()` also accepts a `datetime`, converting
aware values to the active time zone when `USE_TZ=True`.

`HijriDate` is a frozen dataclass with `year`, `month`, `day`, and
`month_length`. `format_hijri_date()` renders it with full month names:
Arabic for `ar`, Persian for `fa`, Urdu for `ur`, and an English
transliteration otherwise. `long` writes the day, month, and year; `medium`
zero-pads the day; `short` writes `dd/mm/yyyy`. Digits follow `NUMERALS` and
the locale's numbering system, and the era suffix (`هـ`, `هجری قمری`, `ہجری`,
or `AH`) is included unless `suffix=False`.

```python
from datetime import date

from django_rtl_admin import format_hijri_date, from_hijri, to_hijri

hijri = to_hijri(date(2024, 3, 11))
assert (hijri.year, hijri.month, hijri.day) == (1445, 9, 1)
assert from_hijri(1445, 9, 1) == date(2024, 3, 11)
assert format_hijri_date(date(2024, 3, 11), language="ar-eg") == "١ رمضان ١٤٤٥ هـ"
assert format_hijri_date(date(2024, 3, 11), language="en", suffix=False) == "1 Ramadan 1445"
```

In templates, use the `hijri_date` filter from `{% load rtl_admin %}`:

```html
{% load rtl_admin %}
{{ book.published_on|hijri_date }}
{{ book.published_on|hijri_date:"short" }}
```

::: django_rtl_admin.hijri
    options:
      heading_level: 3
      members:
        - HijriDate
        - to_hijri
        - from_hijri


## CSV export

`export_as_csv(modeladmin, request, queryset)` is a Django admin action that
exports the selected rows as a spreadsheet-safe UTF-8 CSV stream. It works on
any `ModelAdmin`; `BidiSafeAdminMixin` is not required. See the
[admin mixin guide](admin-mixin.md#csv-export) for adding it to `actions` and
the full behavior list.

`make_csv_export_action(fields=None, *, filename=None, digits="latn",
header="verbose", bom=True, delimiter=",")` returns the same action with
custom options. Invalid `digits`, `header`, or `delimiter` values raise
`ValueError`.

```python
from django_rtl_admin import export_as_csv, make_csv_export_action

native_digits = make_csv_export_action(digits="native", delimiter=";")
```

Both actions are decorated with `admin.action(permissions=["view"])` and a
translated label, check the model's view permission (`PermissionDenied`
otherwise), stream rows through `StreamingHttpResponse` and
`QuerySet.iterator()`, strip Unicode bidi control characters, convert
Arabic-Indic and Persian digits with `transliterate_digits()` (leaving ISO 8601
date/datetime/time cells in ASCII), format dates and datetimes as ISO 8601 in
the current time zone, resolve related `field__subfield` lookups on every
supported Django, prefix cells starting with `=`, `+`, `-`, `@`, tab, or
carriage return with an apostrophe, and send an RFC 6266 `Content-Disposition`
filename with a UTF-8 BOM by default. Each factory action gets a distinct
`__name__` derived from its options, so several can share one `ModelAdmin`.

::: django_rtl_admin.actions
    options:
      heading_level: 3
      members:
        - export_as_csv
        - make_csv_export_action
