# Python API

Use these helpers in display methods, custom templates, or other presentation
code. They read Django's active language and the [configuration](configuration.md);
run them inside a configured Django application. They do not change stored model
values. The reference below is generated from the Python source with mkdocstrings.

## Choosing an isolation helper

- `isolate()` wraps an entire plain-text value; use `direction="ltr"` for an
  opaque identifier such as an ISBN.
- `isolate_runs()` isolates opposite-direction fragments inside plain-text prose.
- `mark_isolated()` and `mark_isolated_runs()` are the HTML-producing variants.
  Keep `autoescape=True` for untrusted text. Already-safe HTML is trusted, not
  sanitized; the run-level helper leaves it untouched to avoid damaging markup.
- `strip_isolates()` removes the isolate characters and legacy LRM/RLM marks
  understood by this package. It is not a general Unicode-control sanitizer.

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
Without Babel, or with `USE_BABEL=False`, formatting uses Django plus digit
transliteration. An explicit `language` is respected on both paths.

Use `short`, `medium`, `long`, or `full` for portable date/datetime requests.
Without Babel, `short` uses Django's short date/datetime format and the other
three use its regular format. Custom patterns are backend-specific: Babel uses
CLDR patterns and Django uses Django format strings. The time fallback always
uses Django's locale time format, regardless of `fmt`.

`NUMERALS` controls digit shapes, not every separator. `transliterate_digits()`
converts digits among `latn`, `arab`, and `arabext` without changing punctuation.
Formatting helpers return text; apply isolation separately when needed.

::: django_rtl_admin.formatting
    options:
      heading_level: 2
      members:
        - numbering_system
        - transliterate_digits
        - format_number
        - format_currency
        - format_percent
        - format_date
        - format_datetime
        - format_time
