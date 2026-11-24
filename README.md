# django-rtl-admin

[![CI](https://github.com/MarwanMaher0/django-rtl-admin/actions/workflows/ci.yml/badge.svg)](https://github.com/MarwanMaher0/django-rtl-admin/actions/workflows/ci.yml)
[![Coverage](https://coveralls.io/repos/github/MarwanMaher0/django-rtl-admin/badge.svg?branch=main)](https://coveralls.io/github/MarwanMaher0/django-rtl-admin?branch=main)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue)](https://github.com/MarwanMaher0/django-rtl-admin)
[![Django](https://img.shields.io/badge/django-4.2%20%7C%205.x%20%7C%206.x-092e20)](https://www.djangoproject.com/)
[![License](https://img.shields.io/badge/license-MIT-green)](https://github.com/MarwanMaher0/django-rtl-admin/blob/main/LICENSE)

The Django admin is *nearly* bilingual. Switch it to Arabic, Hebrew, Persian or
Urdu and the page does flip — but a specific, repeatable set of things stays
pointing the wrong way, and any value that mixes scripts (an ISBN, an email, a
file path, a version string, a hyphenated date) is quietly reordered on screen.

`django-rtl-admin` fixes those things. It is one app you add to
`INSTALLED_APPS`; it does not replace the admin, restyle it, or ask you to
change your `ModelAdmin` classes. Python 3.10+, Django 4.2 through 6.1.

| English | Arabic (Egypt) |
| --- | --- |
| ![The example admin in English](https://raw.githubusercontent.com/MarwanMaher0/django-rtl-admin/main/docs/admin-en.png) | ![The same admin in Arabic](https://raw.githubusercontent.com/MarwanMaher0/django-rtl-admin/main/docs/admin-ar.png) |

Same project, same `ModelAdmin`, one language switch. Note the Arabic-Indic
digits in the price column, the identifiers that stayed the right way round,
and the language switcher. All English computed properties measured by the
browser suite match the stock admin.

---

## The problem, specifically

Django styles the admin with *physical* CSS properties (`margin-left`,
`padding-right`, `float: left`, `text-align: left`) and then ships a
hand-maintained `admin/css/rtl.css` that flips a subset of them back. Missed
mirror rules can cause visible defects. The numbered cases below start from
`getComputedStyle` measurements on Django 5.2 in an `ar-EG` admin, with notes
on newer versions and cases that already match stock:

1. **The "Add" button's `+` icon does not move.** `.object-tools a.addlink`
   computes `background-position: calc(100% - 7px) 50%; padding-right: 26px` —
   the icon stays on the leading edge instead of the trailing one. There is no
   rule for it in `rtl.css`.
2. **The object-tools buttons run in LTR order before Django 6.0.**
   `.object-tools li` keeps `float: left; margin-left: 5px`; the fix floats right
   with a 5px right margin in RTL. Django 6.0+ (including 6.1) uses inline-block
   items without floats, which the package preserves in both languages; the
   first item's margins stay zero, so that case checks stock parity.
3. **The action dropdown's gap is on the wrong side.**
   `#changelist .actions select` keeps `margin-left: 10px`.
4. **The date/time widget's margins are not mirrored.** Both split-widget
   inputs retain stock LTR left/right margins: 5px/2px before Django 6.1 and
   0/2px on 6.1+. The fix mirrors these exactly in RTL to 2px/5px and 2px/0,
   respectively, while preserving the stock English margins.
5. **Correction: the stock sidebar chevrons already mirror correctly.** The
   browser mirrors the literal `»`/`«` characters in RTL; the package does not
   swap them. Tests assert stock parity in both expanded and collapsed states,
   not a failing negative control. The earlier claim that unswapped literals
   pointed the wrong way was incorrect.
6. **Aligned field help text has incorrect padding before Django 6.1.**
   Stock RTL left/right padding is 10px/10px, rather than the mirror of stock
   LTR's 10px/3px. The fix uses 3px/10px in RTL and preserves English padding.
   On Django 6.1+ both sides are already zero in both languages and stay so;
   this is a stock-parity case.
7. **English labels render with the colon on the wrong side** — `:Title
   (Arabic)` instead of `Title (Arabic):` — because nothing in the admin is
   direction-aware at the text level.
8. **An English fieldset description, or a field's help text, gets its full
   stop at the *start* of the line**, for the same reason. (`unicode-bidi` is
   not an inherited property and the admin wraps help text in a second `<div>`,
   so fixing this needs the child element named explicitly — which is the kind
   of detail a hand-maintained mirror file is never going to keep up with.)
9. **A path typed into a text input is reordered.**
   `/archive/ar/2024-03-05/file.pdf` displays with the leading slash at the
   other end. The database is fine; the human reads the wrong string.
10. **Whole rules have no RTL counterpart at all:** `.colSM`,
    `.colSM #content-related`, `.colSM #content-main` (the sidebar-left column
    layout), `#content-related .actionlist li` (recent actions),
    `.related-lookup`, `.file-upload .deletelink`, `form div.radiolist div`,
    `form div.radiolist input[type="radio"]`, `form div.radiolist label` (on
    Django 6.1), `.aligned .vCheckboxLabel` (above 767px),
    `.delete-confirmation form .cancel-link`, `.selector-chooseall`,
    `.selector-clearall`, `.selector .selector-filter label`, `.stacked`,
    `.stacked ul.selector-chooser`, `.stacked .selector-chooser li`,
    `blockquote`, and
    `table thead th.sorted .sortoptions a.sortremove::after`.

And one more that is not a bug so much as a gap: **Django's l10n has no concept
of a numbering system.** `django.utils.formats.number_format` will never give
you `١٢٣٤` for `ar-EG`, no matter how you set `USE_THOUSAND_SEPARATOR`, because
CLDR numbering systems are simply not modelled.

---

## Install

```bash
pip install django-rtl-admin

# optional, for CLDR-accurate numbers, dates and currency:
pip install "django-rtl-admin[babel]"
```

Then put the app **above** `django.contrib.admin`, so its template overrides win:

```python
INSTALLED_APPS = [
    "django_rtl_admin",  # must come first
    "django.contrib.admin",
    ...,
]
```

A system check (`rtl_admin.W001`) tells you if you get the order wrong.

For the language switcher you also need `LocaleMiddleware` and the `set_language`
view, which is the standard Django i18n setup:

```python
MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",  # <-- here
    "django.middleware.common.CommonMiddleware",
    ...,
]

LANGUAGES = [("en", "English"), ("ar-eg", "Arabic (Egypt)")]
USE_I18N = True
```

```python
# urls.py
urlpatterns = [
    path("admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),
]
```

Checks `rtl_admin.W003` and `rtl_admin.W004` flag both of those if they are
missing, and the switcher renders nothing rather than raising.

When you deploy, set `STATIC_ROOT` and run `python manage.py collectstatic` as
for any app with static files; that copies the stylesheet and switcher script.

That is the whole installation. Everything below is optional.

---

## Quickstart

### Stop identifiers being reordered in the changelist and read-only fields

```python
from django.contrib import admin
from django_rtl_admin import BidiSafeAdminMixin


@admin.register(Book)
class BookAdmin(BidiSafeAdminMixin, admin.ModelAdmin):
    list_display = ("title_ar", "isbn", "edition", "catalogue_path", "published_on")
    readonly_fields = ("archive_note",)
```

Every changelist cell is now wrapped in a Unicode isolate, and embedded
opposite-direction runs inside `readonly_fields` on the change form are isolated
too. Column headers, sort links, `column-<name>` / `field-<name>` CSS classes,
field labels, help text and the link to the change form are unchanged; boolean
fields (which render as icons), `SafeString` HTML values and anything in
`list_editable` are not wrapped.

The object's name is isolated as well where the admin quotes it: on the delete
confirmation page and in the "added", "changed" and "deleted" messages.

### Parse prices and dates with Arabic-Indic or Persian digits

With the mixin above, Django can parse `١٬٢٣٤٫٥٠` as `1234.50` or `۲۰۲۴-۰۳-۰۵`
as `2024-03-05` in any UI language. This works on admin-generated integer,
decimal, float, date, time, and datetime fields (including split date/time),
`list_editable` fields, and inlines that themselves use the mixin. Normalization
runs in the field's `to_python()`, so it preserves the original bound form data
and uses Django's decimal separator for localized numeric fields. Dates are
Gregorian only; Jalali and Hijri dates are not converted.

For the same conversion in your own form, import `normalize_numeric_input` from
`django_rtl_admin`. See the [Python API](https://marwanmaher0.github.io/django-rtl-admin/api/#normalizing-numeric-input)
for the exact characters it handles.

### In your own templates

```django
{% load rtl_admin %}

{{ book.isbn|bidi_isolate }}              {# 978-0-262-03561-3, the right way round #}
{{ note|bidi_runs }}                      {# isolate only the embedded runs #}
{{ book.price|l10n_currency:"EGP" }}      {# ٣٤٩٫٩٠ ج.م.‏ in ar-EG, EGP349.90 in en #}
{{ book.published_on|l10n_date:"long" }}
<td dir="{{ value|bidi_dir }}">{{ value }}</td>
```

### In Python

```python
from django_rtl_admin import mark_isolated, format_currency, format_number


@admin.display(description="Reference")
def reference(self, obj):
    return mark_isolated(obj.reference)  # escaped first, then isolated


format_number(1234567.891, language="ar-eg")  # '١٬٢٣٤٬٥٦٧٫٨٩١'
format_currency("349.90", "EGP", language="ar-eg")
```

---

## What you get

### 1. Direction-aware admin styling

A template override (`admin/base_site.html`) and a stylesheet that restates the
admin's physical rules with **logical properties** — `margin-inline-start`,
`padding-inline-end`, `inset-inline-start`, `text-align: start`,
`float: inline-end`. Logical properties express spacing in either direction;
all English computed properties measured by the browser suite match stock.
Version gates preserve changes in Django's own layout: the object-tools `li`
float/margin fix, including its CSS media-query rule, is scoped to the body class
`rtl-admin--pre-6-0`, leaving Django 6.0+ inline-block/no-float items untouched in
both languages. Datetime margins and aligned help padding also follow Django's
6.1 layout change. Direction-specific rules handle sprite offsets and mirrored
icons; sidebar chevrons are left to the browser's Unicode mirroring.

It covers the sidebar, the changelist, the filter column, the object-tools bar,
the action bar, the paginator, aligned forms, inlines, the date/time widgets,
the many-to-many selector, select2 autocompletes and the login page — the places
where stock RTL support runs out.

The stylesheet is linked from the `responsive` block of `admin/base.html`, which
is the last stylesheet hook there is, so it wins over both
`admin/css/rtl.css` and `admin/css/responsive_rtl.css`.

The package also overrides `admin/change_list_results.html`,
`admin/edit_inline/tabular.html`, and `admin/widgets/split_datetime.html` to
label action checkboxes, inline fields and deletion controls, and date/time
inputs accessibly. A project's own override of any of these templates takes
precedence and loses the corresponding accessible labels unless it merges the
package's markup; the stylesheet and other template overrides remain active.

Two CSS-level safety nets come with it, both opt-out:

- `unicode-bidi: isolate` on changelist cells, so one mixed-direction value
  cannot drag its neighbours around inside a row;
- `unicode-bidi: plaintext` on text inputs and textareas — the CSS equivalent
  of `dir="auto"`. Each field picks its own direction from what was actually
  typed into it, which is what a bilingual data-entry form needs.

Labels, legends and read-only values keep their existing plaintext safety nets
in both languages. Help text (both the outer element and its inner wrapper) and
fieldset descriptions, including their direct children, use `plaintext` **only
in RTL**; English keeps stock `unicode-bidi: isolate` on these elements. The
input/textarea opt-out does not disable these label, legend, read-only, help or
description rules.

### 2. Bidirectional text safety

The Unicode Bidirectional Algorithm reorders text at display time. That is
right for prose and wrong for identifiers. The fix is Unicode *isolates* —
U+2066 LRI, U+2067 RLI, U+2068 FSI, terminated by U+2069 PDI — which are plain
characters, not markup, so they survive escaping, copy-and-paste, `json.dumps`
and database round-trips.

```python
>>> from django_rtl_admin import isolate, isolate_runs, mark_isolated
>>> isolate("v1.2.3")
'⁨v1.2.3⁩'
>>> isolate_runs("مرحبا /srv/archive/report.pdf", base="rtl")
'مرحبا ⁦/srv/archive/report.pdf⁩'
>>> mark_isolated("<script>alert(1)</script>")     # escapes, then isolates
'⁨&lt;script&gt;alert(1)&lt;/script&gt;⁩'
```

`isolate()`, `isolate_runs()`, and their `mark_isolated*` counterparts strip any
existing Unicode `Bidi_Control` characters before wrapping, so an embedded `PDI`
or directional override cannot break out of the isolate and reorder surrounding
text. `mark_isolated()` escapes before it wraps, and `mark_isolated_runs()`
isolates the raw text before escaping so that an isolate character can never
land inside an HTML entity. Values already marked safe are honoured by
`mark_isolated()` just as `conditional_escape` honours them, while
`mark_isolated_runs()` leaves already-safe markup untouched.

`isolate_runs()` is the smarter of the two: it walks the string and wraps only
the parts the algorithm would actually reorder — Latin words inside Arabic
prose, and, in an RTL paragraph, punctuated numeric runs such as `2024-03-05`,
`1.2.3` or `10:45:02`. A bare `1234` is left alone, because it renders
correctly on its own. Punctuation glued to a run travels with it (the leading
slash of a path is exactly the character that jumps otherwise); punctuation
separated by a space stays with the surrounding sentence.

### 3. Locale-aware formatting

Arabic locales do not agree on how to write a number. `ar-EG` uses Arabic-Indic
digits with U+066C as the group separator and U+066B as the decimal separator;
`ar-MA` and plain `ar` use Latin digits with the usual comma and full stop. CLDR
knows this; Django does not model it at all.

```python
>>> from django_rtl_admin import format_number, numbering_system
>>> numbering_system("ar-eg"), numbering_system("ar"), numbering_system("fa")
('arab', 'latn', 'arabext')
>>> format_number(1234567.891, language="ar-eg")
'١٬٢٣٤٬٥٦٧٫٨٩١'
>>> format_number(1234567.891, language="en")
'1,234,567.891'
```

[Babel](https://babel.pocoo.org/) is used when it is installed. Without it,
numbers render from built-in CLDR tables (matching Babel's digits, separators,
and grouping for supported locales, falling back to `django.utils.formats` plus
digit transliteration for others) and dates and times use Django formatting plus
digit transliteration — install the `babel` extra (see Install) for full CLDR
currency, percentage, date and time patterns, though nothing here raises
without it.

### 4. A language switcher

Rendered into the admin header (and onto the login page), listing
`settings.LANGUAGES`, posting to `set_language`, preserving the current admin
URL through `next`. It is a plain `<select>` and a submit button, so it works
with JavaScript disabled; a small deferred script hides the button and submits
on change when JavaScript is available. No inline scripts, no inline styles, no
CDN.

It renders nothing — silently, no exception — when it is switched off, when
fewer than two languages are configured, or when `set_language` is not routed.

---

## Settings

Everything lives in one dict. Every key is optional; every feature is opt-out.

```python
RTL_ADMIN = {
    "CURRENCY": "EGP",
    "LANGUAGE_SWITCHER_LABELS": "both",
}
```

| Key | Default | What it does |
| --- | --- | --- |
| `ENABLE_CSS` | `True` | Link the direction-aware stylesheet into the admin `<head>`. |
| `FONT_STACK` | `None` | Override the `--rtl-admin-font-stack` custom property. A string or a sequence of family names. |
| `EXTRA_RTL_LANGUAGES` | `()` | Language codes to treat as RTL on top of the ones in Django's `LANGUAGES_BIDI`. |
| `ISOLATION_DIRECTION` | `"auto"` | Default isolate used by `bidi_isolate` and the mixin: `"auto"` (FSI), `"ltr"` (LRI) or `"rtl"` (RLI). |
| `ISOLATE_CHANGELIST` | `True` | Let `BidiSafeAdminMixin` isolate changelist cells, and object names on the delete page and in plain-text messages. |
| `ISOLATE_READONLY_FIELDS` | `True` | Let `BidiSafeAdminMixin` isolate embedded opposite-direction runs in change-form `readonly_fields`. |
| `ISOLATE_TABLE_CELLS` | `True` | CSS-level `unicode-bidi: isolate` on changelist cells, linked object names in messages, the change-form subtitle and object links on the delete pages. |
| `PLAINTEXT_FORM_FIELDS` | `True` | CSS-level `unicode-bidi: plaintext` on text inputs and textareas. |
| `NORMALIZE_INPUT_DIGITS` | `True` | Normalize Arabic-Indic and Persian digits in numeric, date, and time input on mixin-enabled admins. Must be a boolean. |
| `NUMERALS` | `"auto"` | Numbering system for the formatting helpers: `"auto"` follows the locale, or force `"latn"`, `"arab"` or `"arabext"`. |
| `USE_BABEL` | `True` | Use Babel when it is installed. `False` skips Babel and uses the built-in CLDR number tables plus Django date/time formatting. |
| `CURRENCY` | `"USD"` | Default currency for `format_currency` / `l10n_currency`. |
| `LANGUAGE_SWITCHER` | `True` | Render the switcher in the admin header. |
| `LANGUAGE_SWITCHER_LANGUAGES` | `None` | `None` means `settings.LANGUAGES`; otherwise a sequence of codes or `(code, label)` pairs. |
| `LANGUAGE_SWITCHER_LABELS` | `"native"` | `"native"` (العربيّة), `"translated"` (Arabic) or `"both"`. |

Unknown keys (`rtl_admin.W002`), invalid option types (`rtl_admin.W005`), extra
RTL languages missing from `LANGUAGES_BIDI` (`rtl_admin.W006`), and invalid
choices (`rtl_admin.E001`) are reported by `manage.py check`; accessing an
invalid choice at runtime also raises `ImproperlyConfigured`.

---

## Reference

### Template filters — `{% load rtl_admin %}`

| Filter | Example | Notes |
| --- | --- | --- |
| `bidi_isolate` | `{{ v\|bidi_isolate }}`, `{{ v\|bidi_isolate:"ltr" }}` | Wrap the whole value in an isolate. Escapes first; honours `{% autoescape off %}`. |
| `bidi_runs` | `{{ note\|bidi_runs }}`, `{{ note\|bidi_runs:"rtl" }}` | Isolate only the embedded opposite-direction runs. |
| `bidi_strip` | `{{ v\|bidi_strip }}` | Remove every Unicode `Bidi_Control` character (isolates, marks, embeddings and overrides). |
| `bidi_dir` | `<td dir="{{ v\|bidi_dir }}">` | First-strong direction of the value: `"rtl"` or `"ltr"`. |
| `l10n_number` | `{{ n\|l10n_number }}`, `{{ n\|l10n_number:"2" }}` | Locale-aware number in the locale's numbering system. |
| `l10n_currency` | `{{ p\|l10n_currency:"EGP" }}` | Locale-aware money; the argument is optional. |
| `l10n_percent` | `{{ ratio\|l10n_percent }}` | A 0..1 ratio as a percentage. |
| `l10n_timedelta` | `{{ seconds\|l10n_timedelta }}` | Localized duration from seconds or a `timedelta`. |
| `l10n_timesince` | `{{ published_at\|l10n_timesince }}` | Localized relative time with past/future wording. |
| `l10n_filesize` | `{{ upload.size\|l10n_filesize }}` | Locale-aware file size; pass `"binary"` for powers of 1024. |
| `l10n_date` | `{{ d\|l10n_date:"long" }}` | `short`, `medium`, `long`, `full`. |
| `l10n_datetime` | `{{ dt\|l10n_datetime }}` | |
| `l10n_time` | `{{ t\|l10n_time }}` | |
| `local_digits` | `{{ "REF-2024"\|local_digits }}` | Rewrite digits in a ready-made string. |
| `rtl_admin_accessible_viewport` | `{{ block.super\|rtl_admin_accessible_viewport }}` | Remove the stock viewport's pinch-zoom restrictions while preserving the rest of the responsive block. |
| `rtl_admin_result_object` | `{{ cl.result_list\|rtl_admin_result_object:forloop.counter0 }}` | Return the changelist object at the supplied zero-based index. |
| `rtl_admin_action_label` | `{{ item\|rtl_admin_action_label:object }}` | Add an escaped, translated accessible name to a stock changelist action checkbox. |

### Template tags

| Tag | Returns |
| --- | --- |
| `{% rtl_admin_direction %}` | `"rtl"` or `"ltr"` for the active language. |
| `{% rtl_admin_body_class %}` | The `rtl-admin …` class list the stylesheet keys off. |
| `{% rtl_admin_styles %}` | The stylesheet `<link>` plus any `FONT_STACK` override. |
| `{% rtl_admin_scripts %}` | The deferred `<script>` for the switcher. |
| `{% rtl_admin_language_switcher %}` | The switcher form. |
| `{% rtl_admin_language_links %}` | The switcher's languages as plain data, for custom markup. |
| `{% rtl_admin_isolated_join values ", " %}` | Join values, isolating each. |
| `{% rtl_admin_site_name_tag %}` | `h1` or `div`, whichever the running Django's admin CSS expects. |

### Python API

```python
from django_rtl_admin import (
    BidiSafeAdminMixin,
    LRI,
    RLI,
    FSI,
    PDI,
    isolate,
    isolate_runs,
    strip_isolates,
    is_isolated,
    mark_isolated,
    mark_isolated_runs,
    text_direction,
    has_mixed_direction,
    is_rtl_language,
    current_direction,
    numbering_system,
    normalize_numeric_input,
    transliterate_digits,
    format_number,
    format_currency,
    format_percent,
    format_timedelta,
    format_filesize,
    format_date,
    format_datetime,
    format_time,
    rtl_settings,
)
```

### `BidiSafeAdminMixin`

| Attribute | Default | What it does |
| --- | --- | --- |
| `bidi_isolate_changelist` | `None` | `True`/`False` overrides `RTL_ADMIN["ISOLATE_CHANGELIST"]` for this admin. |
| `bidi_isolate_readonly` | `None` | `True`/`False` overrides `RTL_ADMIN["ISOLATE_READONLY_FIELDS"]` for this admin. |
| `bidi_normalize_input` | `None` | Inherit `RTL_ADMIN["NORMALIZE_INPUT_DIGITS"]`, or use `True` or `False` to override it for this admin. |
| `bidi_isolate_fields` | `None` | Restrict changelist isolation to these `list_display` entries. |
| `bidi_isolate_exclude` | `()` | Leave these `list_display` or `readonly_fields` entries alone. |
| `bidi_isolation_direction` | `None` | `"auto"`, `"ltr"` or `"rtl"` for changelist cells on this admin. |

### System checks

| ID | Meaning |
| --- | --- |
| `rtl_admin.E001` | A choice setting (`ISOLATION_DIRECTION`, `NUMERALS` or `LANGUAGE_SWITCHER_LABELS`) has an unsupported value. |
| `rtl_admin.W001` | `django_rtl_admin` is listed after `django.contrib.admin`, so the template overrides will not apply. |
| `rtl_admin.W002` | `RTL_ADMIN` contains keys this app does not understand. |
| `rtl_admin.W003` | The switcher is on but `set_language` cannot be reversed. |
| `rtl_admin.W004` | `LocaleMiddleware` is not installed, so a chosen language will not stick. |
| `rtl_admin.W005` | `RTL_ADMIN` is not a mapping or `None`, or a checked setting has the wrong type (e.g. `"false"` instead of `False`, or a bare string for `EXTRA_RTL_LANGUAGES`). |
| `rtl_admin.W006` | `RTL_ADMIN["EXTRA_RTL_LANGUAGES"]` lists language codes missing from `settings.LANGUAGES_BIDI`. |
| `rtl_admin.W007` | The switcher is on and `LocaleMiddleware` is before `SessionMiddleware` or after `CommonMiddleware`. |
| `rtl_admin.W008` | The switcher is on and `RTL_ADMIN["LANGUAGE_SWITCHER_LANGUAGES"]` lists codes missing from `settings.LANGUAGES`. |

---

## Keeping your own `admin/base_site.html`

The app ships `admin/base_site.html`, which does nothing but extend
`django_rtl_admin/base_site.html`. If your project needs its own, extend the
latter and you keep everything:

```django
{% extends "django_rtl_admin/base_site.html" %}

{% block branding %}
  <div id="site-name">Acme</div>
{% endblock %}
```

---

## Browser support

The stylesheet uses CSS logical properties (`margin-inline-start`,
`inset-inline-end`, `float: inline-start`), `unicode-bidi: plaintext` and
`color-mix()`. All are available in Chrome/Edge 118+, Firefox 115+ and
Safari 16.2+. Older browsers fall back to Django's own `rtl.css`, which is what
they would have had anyway.

---

## The example project

```bash
git clone https://github.com/MarwanMaher0/django-rtl-admin
cd django-rtl-admin
pip install -e ".[babel]"

cd example
python manage.py migrate
python manage.py demodata        # creates the superuser and sample records
python manage.py runserver
```

Then open <http://127.0.0.1:8000/admin/> and log in as `demo` / `demo12345`.
The library app has a model with parallel English and Arabic fields, an inline,
an autocomplete, a date hierarchy, filters and the sorts of values that break
under bidi. Use the switcher in the header to flip between English, Arabic and
Arabic (Egypt); `ar` and `ar-eg` differ only in their numbering system, which
is the point. Kurdish Sorani, Hebrew, Persian, Uyghur and Urdu catalogs ship
with the package; add their codes to `LANGUAGES` to try them in the demo.

---

## Tests

```bash
pip install -e ".[test]"
pytest
ruff check .
ruff format --check .
```

The suite covers the isolation helpers across many input shapes, autoescape
correctness (HTML in a value must stay escaped, in Python and through the
changelist), filter and tag registration, numbering-system formatting with and
without Babel, the mixin applied to a real changelist, the language switcher,
the settings namespace, the system checks, and the fact that the template
overrides resolve ahead of `django.contrib.admin`.

`noxfile.py` defines one test cell for every Python/Django pair that Django
itself supports — Python 3.10 to 3.14 against Django 4.2, 5.0, 5.1, 5.2, 6.0
and 6.1, 21 cells — plus a Python 3.12 / Django 5.2 cell with Babel
uninstalled, so the fallback path is covered too. CI reads that list from the
noxfile and runs every cell; each run prints its coverage table in the job
summary, and one cell publishes to Coveralls (the badge at the top).

```bash
pip install nox        # or: uvx nox ...
nox -l                                   # list the cells
nox -s "tests(py3.12-django5.2)"         # one cell
nox                                      # everything, then ruff and mypy
```

---

## Licence

MIT. See [LICENSE](https://github.com/MarwanMaher0/django-rtl-admin/blob/main/LICENSE).
