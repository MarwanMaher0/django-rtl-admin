---
title: Template tags and filters | django-rtl-admin
description: Use django-rtl-admin template filters and tags for bidi isolation, locale-aware numbers and dates, direction classes, static assets, and language switching.
---

# Template tags and filters

Load the library in each Django template that uses it:

```django
{% load rtl_admin %}
```

The library contains 14 filters and 8 tags. Examples below assume it is loaded
and that variables come from the template context. Number examples use numeric
values or numeric strings; date/time examples use Python date, datetime, or time
objects. See [Configuration](configuration.md) for shared defaults and the
[Python API](api.md) for use outside templates.

## Bidirectional text filters

### `bidi_isolate`

Wrap the whole value in a Unicode isolate. The optional direction is `"auto"`,
`"ltr"`, or `"rtl"`; omitting it uses `ISOLATION_DIRECTION` (default `"auto"`).
Use LTR isolation for opaque identifiers:

```django
{{ book.isbn|bidi_isolate:"ltr" }}
```

`None` and empty text render empty. Ordinary HTML is escaped under autoescape;
already-safe HTML is trusted. `{% autoescape off %}` disables escaping. Isolation
adds characters, not an HTML element, and does not detect existing wrappers.

### `bidi_runs`

Isolate only embedded opposite-direction runs in prose. The optional base is
`"ltr"` or `"rtl"`; when omitted it follows the active language, not
`ISOLATION_DIRECTION`. For a context string such as `note = "مرحبا v1.0"`:

```django
{{ note|bidi_runs:"rtl" }}
```

In RTL prose, punctuated numbers such as dates and versions are isolated too;
bare numbers are left alone. Isolation precedes escaping so HTML entities stay
intact. Already-safe strings and objects exposing `__html__` are returned
untouched to avoid damaging markup. Use an ordinary context string, not a safe
template literal, when demonstrating run isolation. `None` renders empty.

### `bidi_strip`

Remove the package's LRI, RLI, FSI, PDI, LRM, and RLM characters:

```django
{{ reference|bidi_isolate:"ltr"|bidi_strip }}
```

`None` renders empty. This does not remove every Unicode directional control
and is not an HTML sanitizer. Safe-input status is preserved.

### `bidi_dir`

Return `"rtl"` or `"ltr"` from the first strong character. The optional fallback
is `"ltr"` by default; numbers, punctuation, empty text, and `None` use it:

```django
<span dir="{{ reference|bidi_dir:"rtl" }}">{{ reference }}</span>
```

The fallback is not validated; use `"ltr"` or `"rtl"`. This is content direction,
not the active language's direction.

## Locale-aware formatting filters

These filters use the active language, `NUMERALS`, and `USE_BABEL`. To select a
language for a block, also load `i18n` and use Django's `{% language %}` tag.
Formatting does not itself add Unicode isolates; chain `bidi_isolate` if needed.
Like Django's built-in filters, they fail silently: numeric filters return
nonnumeric or non-finite input as text, invalid dates and times render empty,
and a malformed decimal-position argument is ignored. Numeric strings, including
exponent notation and surrounding whitespace, are normalized before formatting.
The Python `format_currency()` helper is strict instead, raising `ValueError` for
nonempty, nonnumeric, or non-finite input.

### `l10n_number`

Format a number with grouping and locale digits. The optional argument selects
decimal positions; omitting it leaves precision to the backend:

```django
{{ amount|l10n_number:"2" }}
```

For `amount = 2.5` in English, this renders `2.50`. A nonempty precision argument
that is not an integer is ignored. `None` or empty input renders empty.
Nonnumeric text passes through unchanged. This filter does not expose a grouping
argument.

### `l10n_currency`

Format money using an optional currency code; the default is `CURRENCY` (`"USD"`):

```django
{{ book.price|l10n_currency:"EGP" }}
```

Babel supplies locale-specific patterns. Fallback output is a localized number
with two decimal places, a nonbreaking space, and the currency code. `None` or
empty input renders empty; an empty currency argument uses the configured default.
Nonnumeric input renders unchanged rather than producing a malformed amount.

### `l10n_percent`

Format a ratio as a percentage, with no filter argument:

```django
{{ ratio|l10n_percent }}
```

For `ratio = 0.256`, English output begins with `26`. Input is normally a `0..1`
ratio, but that range is not enforced. The Django fallback multiplies by 100,
rounds half up to a whole number, and appends `%`. Empty input renders empty;
nonnumeric input renders unchanged.

### `l10n_date`

Format a date. The optional style defaults to `"medium"`:

```django
{{ book.published_on|l10n_date:"long" }}
```

Use `"short"`, `"medium"`, `"long"`, or `"full"`. Custom patterns depend on the
backend. `None` and invalid date values render empty; localized digits follow
`NUMERALS`.

### `l10n_datetime`

Format a datetime. The optional style defaults to `"medium"`:

```django
{{ updated_at|l10n_datetime:"short" }}
```

Styles and custom-pattern behavior match `l10n_date`. `None` and invalid datetime
values render empty. Both `l10n_datetime` and `l10n_time` register
`expects_localtime=True`, so
Django converts aware `datetime` values to the active time zone when `USE_TZ`
is enabled and leaves them as given inside `{% localtime off %}` (or when
`USE_TZ=False`).

### `l10n_time`

Format a time or datetime. The optional style defaults to `"medium"`:

```django
{{ opening_time|l10n_time:"short" }}
```

Babel honors the style; the Django fallback always uses the locale's time format,
ignoring the argument. `None` and invalid time values render empty.

### `local_digits`

Rewrite digit shapes in an already-formatted string, without changing punctuation:

```django
{{ "REF-2024"|local_digits }}
```

With automatic numerals in `ar-eg`, this renders `REF-٢٠٢٤`. Conversion recognizes
Latin, Arabic-Indic, and extended Arabic-Indic input digits. `None` renders empty;
nonnumeric text passes through unchanged, as does the original value if conversion
fails.

### Backend differences

Without Babel, date/datetime `"short"` uses Django's short format; `"medium"`,
`"long"`, and `"full"` all use its regular format. Custom Babel CLDR patterns and
Django format strings are not interchangeable. These filters have no language,
timezone, or numbering-system argument; use settings, language activation, or
the [Python formatting API](api.md) where appropriate.

## Direction and asset tags

All tags except `rtl_admin_language_switcher` are simple tags and support
`as variable` to capture their result. Context-taking tags receive context
automatically; do not pass it as a template argument.

### `rtl_admin_direction`

Return `"rtl"` or `"ltr"` for the active language, including extra RTL languages:

```django
<section dir="{% rtl_admin_direction %}">{{ content }}</section>
```

### `rtl_admin_body_class`

Return the stylesheet's body classes:

```django
<body class="{% rtl_admin_body_class %}">
  {{ content }}
</body>
```

The result starts with `rtl-admin rtl-admin--rtl` or `rtl-admin rtl-admin--ltr`.
It then includes `rtl-admin--isolate-cells` and `rtl-admin--plaintext-fields`
when their settings are enabled, even if `ENABLE_CSS=False`.

### `rtl_admin_site_name_tag`

Return the branding element name: `h1` before Django 5.0, otherwise `div`:

```django
{% rtl_admin_site_name_tag as site_name_tag %}
<{{ site_name_tag }} id="site-name">{{ site_header }}</{{ site_name_tag }}>
```

### `rtl_admin_styles`

Emit the stylesheet link and any `FONT_STACK` override:

```django
{% rtl_admin_styles %}
```

Output is empty with `ENABLE_CSS=False`. URLs use Django's static-file handling.
A `csp_nonce` supplied in context is attached to the link and optional style tag.

### `rtl_admin_scripts`

Emit the deferred language-switcher script:

```django
{% rtl_admin_scripts %}
```

Output is empty with `LANGUAGE_SWITCHER=False`; otherwise it can appear even
when the form is hidden because of its language count or missing URL. It also
uses the context's `csp_nonce` when available. The package does not create nonces.

The shipped admin base already invokes the body-class, style, script, and
branding tags. Use these individually for custom templates rather than loading
assets twice. See [Installation](installation.md) for template inheritance.

## Language and collection tags

### `rtl_admin_language_switcher`

Render the switcher form:

```django
{% rtl_admin_language_switcher %}
```

This inclusion tag has no `as variable` form. It renders nothing when disabled,
when fewer than two language rows exist, or when reversing `set_language` raises
`NoReverseMatch`. Missing `LocaleMiddleware` does not hide the form.

The form POSTs the selected `language`, CSRF token, and `next` to `set_language`.
`next` is the current request's full path including query string, or empty without
a request. Use a normal request/CSRF-aware template context. JavaScript submits
on selection changes and hides the button; without it, the submit button works.
See [Quick start](quick-start.md) and [System checks](system-checks.md).

### `rtl_admin_language_links`

Return plain data for custom markup, not prebuilt hyperlinks:

```django
{% rtl_admin_language_links as languages %}
<ul>
  {% for language in languages %}
    <li lang="{{ language.code }}"
        dir="{% if language.bidi %}rtl{% else %}ltr{% endif %}">
      {{ language.label }}{% if language.is_active %} — active{% endif %}
    </li>
  {% endfor %}
</ul>
```

Each dictionary has `code`, `label`, `bidi`, and `is_active`; there is no URL key.
The tag returns data even when the switcher is disabled or its endpoint is absent.
Active selection compares lowercase codes exactly, without regional fallback.
Language order and duplicates are retained. See [Configuration](configuration.md)
for label modes and the source of the language list.

### `rtl_admin_isolated_join`

Join an iterable, isolating each value with `ISOLATION_DIRECTION`:

```django
{% rtl_admin_isolated_join references "; " %}
```

For example, `references` can be `["ISBN-123", "REF-456"]`. The optional separator
defaults to `", "`. An empty iterable or `None` renders empty; pass a collection,
not a string unless you intend to join individual characters. Ordinary values
and separators are escaped, while safe HTML is trusted. Value escaping remains
on even inside `{% autoescape off %}`. The separator itself is not isolated.
