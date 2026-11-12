---
title: Configuration reference | django-rtl-admin
description: Configure all 13 RTL_ADMIN settings for logical styling, Unicode isolation, numeral systems, Babel formatting, and admin language-switcher behavior.
---

# Configuration

Configure the package through the `RTL_ADMIN` dictionary in Django settings.
Every key is optional; omitted keys retain their defaults. Start with
[Installation](installation.md) and [Quick start](quick-start.md) before changing
individual features.

```python
RTL_ADMIN = {
    "CURRENCY": "EGP",
    "LANGUAGE_SWITCHER_LABELS": "both",
}
```

## Complete settings reference

These are all 13 supported keys, defined in `django_rtl_admin.conf.DEFAULTS`.

| Key | Default | Effect |
| --- | --- | --- |
| `ENABLE_CSS` | `True` | Emit the package stylesheet link and any inline font override through `rtl_admin_styles`. |
| `FONT_STACK` | `None` | Override `--rtl-admin-font-stack` with a string or sequence of family names; `None` retains the shipped stack. |
| `EXTRA_RTL_LANGUAGES` | `()` | Add language codes to the RTL languages already in Django's `LANGUAGES_BIDI`. |
| `ISOLATION_DIRECTION` | `"auto"` | Default whole-value isolate: `"auto"` (FSI), `"ltr"` (LRI), or `"rtl"` (RLI). |
| `ISOLATE_CHANGELIST` | `True` | Enable isolation in admins that explicitly use `BidiSafeAdminMixin`, unless overridden per admin. |
| `ISOLATE_TABLE_CELLS` | `True` | Add the body class enabling CSS isolation for changelist cells and related navigation/data containers. |
| `PLAINTEXT_FORM_FIELDS` | `True` | Add the body class enabling first-strong plaintext direction for text-like inputs and textareas. |
| `NUMERALS` | `"auto"` | Follow the locale's numbering system, or force `"latn"`, `"arab"`, or `"arabext"` in the formatting helpers. |
| `USE_BABEL` | `True` | Use Babel when installed; otherwise use Django formatting plus digit transliteration. |
| `CURRENCY` | `"USD"` | Default currency for `format_currency` and `l10n_currency` when no truthy currency argument is supplied. |
| `LANGUAGE_SWITCHER` | `True` | Enable the switcher form, its progressive-enhancement script, and checks W003/W004. |
| `LANGUAGE_SWITCHER_LANGUAGES` | `None` | Use `settings.LANGUAGES`, or provide a sequence of codes or `(code, label)` pairs. |
| `LANGUAGE_SWITCHER_LABELS` | `"native"` | Choose native labels, configured/English labels with `"translated"`, or both with `"both"`. |

## Styling and direction

`ENABLE_CSS=False` suppresses both the stylesheet link and the `FONT_STACK`
override. It does not disable Unicode isolation, formatting, body-class output,
or the switcher script. Existing Django admin styles remain independent.

`FONT_STACK` applies to RTL bodies and their inputs, textareas, selects, and
buttons. The tag serializes it as a CSS `font-family` list inside a `<style>`
element:

- A string is read as a CSS family list, for example
  `'"Noto Naskh Arabic", Tahoma, serif'`. Unquoted names may contain spaces;
  a quote or backslash belongs inside a quoted name.
- A sequence holds one family name per entry, raw (`"Noto Naskh Arabic"`) or
  already quoted (`'"Noto Naskh Arabic"'`). An entry containing a comma is a
  single name.
- Every family name is emitted as a double-quoted CSS string, with `\` and `"`
  escaped. Generic keywords (`serif`, `sans-serif`, `monospace`, `cursive`,
  `fantasy`, `system-ui`, `ui-serif`, `ui-sans-serif`, `ui-monospace`,
  `ui-rounded`, `math`, `emoji`, `fangsong`) and the `-apple-system` and
  `BlinkMacSystemFont` system-font keywords stay bare unless you quote them.

```python
RTL_ADMIN = {
    "FONT_STACK": ("Noto Naskh Arabic", "Tahoma", "sans-serif"),
    "EXTRA_RTL_LANGUAGES": ("tzm",),
}
```

This emits
`:root { --rtl-admin-font-stack: "Noto Naskh Arabic", "Tahoma", sans-serif; }`,
and so does the string `'"Noto Naskh Arabic", Tahoma, sans-serif'`.

Falsy values emit no override. A value that is malformed, for example an
unterminated quote, or a family containing `<`, `>`, `{`, `}`, `;` or a control
character, could close the `<style>` element or the CSS rule. The tag then
skips the override, logs a warning on the `django_rtl_admin` logger, and the
shipped stack applies.

Extra RTL languages affect the direction tag, body classes, switcher option
`dir`, and the default base of `bidi_runs`. Direction detection also reads
Django's `LANGUAGES_BIDI` with the same base-code matching as
`get_language_bidi()`, so a code added to `LANGUAGES_BIDI` gets matching
`rtl-admin--rtl` body classes. Codes in `EXTRA_RTL_LANGUAGES` that are missing
from `LANGUAGES_BIDI` trigger `rtl_admin.W006`: Django would leave `<html dir>`
at LTR while the package turns the body RTL. Prefer lowercase, hyphenated codes;
regional codes can inherit their base language's direction. These settings do
not add languages to `LANGUAGES`, install translations, or change Babel data.
The stylesheet supplies body direction for extra languages; it does not rewrite
Django's `<html dir>` attribute. See [System checks](system-checks.md#rtl_adminw006-extra-rtl-language-missing-from-languages_bidi).

`ISOLATE_TABLE_CELLS` gates `unicode-bidi: isolate` on changelist body cells,
tabular-inline cells, breadcrumbs, content headings, object-tool links, and
changelist-filter links. It works in either UI direction and does not insert
characters into values.

`PLAINTEXT_FORM_FIELDS` gates `unicode-bidi: plaintext; text-align: start` on
text, email, URL, search, and telephone inputs, inputs without a `type`, and
textareas. Each field or textarea paragraph resolves its own direction.

These two switches are not comprehensive bidi off-switches: while the stylesheet
is loaded, labels, help text, descriptions, and read-only values still receive
plaintext rules. URL widgets, username/password inputs, UUID widgets, and code
also retain their dedicated LTR/isolation rules.

## Unicode isolation

`ISOLATION_DIRECTION` chooses the opener for whole-value isolation:

| Value | Opener | Meaning |
| --- | --- | --- |
| `"auto"` | FSI, U+2068 | Determine direction from the first strong character. |
| `"ltr"` | LRI, U+2066 | Force left-to-right direction inside the isolate. |
| `"rtl"` | RLI, U+2067 | Force right-to-left direction inside the isolate. |

All three end with PDI, U+2069. The default is used by `bidi_isolate`, isolated
joins, the parenthesized half of `"both"` language labels, and mixin wrappers
without a per-admin direction. `bidi_runs` instead defaults to the active
language's direction.

`ISOLATE_CHANGELIST` does nothing to a plain `ModelAdmin`: opt in with the
[admin mixin](admin-mixin.md). Its `bidi_isolate_changelist` attribute overrides
the global switch. CSS isolation and Unicode isolation are independent, so
disabling one does not disable the other.

## Numbers, currencies, and Babel

`NUMERALS` selects these digit shapes:

| Value | Digits |
| --- | --- |
| `"latn"` | `0123456789` |
| `"arab"` | `٠١٢٣٤٥٦٧٨٩` |
| `"arabext"` | `۰۱۲۳۴۵۶۷۸۹` |

With `"auto"`, the helpers use Babel's locale default when it names a supported
numbering system. An unsupported, nonempty Babel system name selects Latin
digits. Without a Babel locale or its numbering-system default, the helpers use
the package's fallback mapping. Plain `ar` uses Latin digits, `ar-eg` uses
Arabic-Indic digits, and `fa` uses extended Arabic-Indic digits.

Forcing `NUMERALS` changes digit characters, not every separator or currency
pattern. `USE_BABEL=False` forces Django formatting, but still localizes digits.
Missing Babel is handled the same way. Currency fallback is a two-decimal number,
a nonbreaking space, and the currency code; percentage fallback uses a rounded
whole percentage. Date/time fallback details are in the [Python API](api.md).

These settings affect explicit formatting helpers and [filters](template-tags.md),
not every admin field. The mixin uses Django's normal field-display formatting.

## Language switcher

Configure the available Django languages first; the switcher's custom list only
controls which rows it offers. Codes-only and `(code, label)` entries are accepted:

```python
LANGUAGES = [("en", "English"), ("ar-eg", "Arabic (Egypt)")]
RTL_ADMIN = {
    "LANGUAGE_SWITCHER_LANGUAGES": ["en", ("ar-eg", "Arabic (Egypt)")],
    "LANGUAGE_SWITCHER_LABELS": "both",
}
```

`None` uses `LANGUAGES`; an empty sequence offers no languages. Order is retained.
The form hides when disabled, when fewer than two rows exist, or when
`set_language` cannot be reversed with `NoReverseMatch`. Missing middleware does
not hide it. Follow [Quick start](quick-start.md) for the endpoint and middleware.

Labels are selected as follows:

- `"native"`: Django's local language name, falling back to its name or code;
  configured labels are ignored for known codes.
- `"translated"`: the configured label, otherwise Django's English `name` or code.
  Plain strings are not automatically translated; use lazy-translated labels
  when needed.
- `"both"`: native plus an isolated parenthesized configured/English label, unless
  the two labels are equal. Unknown codes use their configured label or code.

Disabling `LANGUAGE_SWITCHER` also suppresses its script and checks
`rtl_admin.W003`/`rtl_admin.W004`. The data-only `rtl_admin_language_links` tag
remains available. With the switch enabled, the script and checks can remain
active even if the form hides because of the language count or URL routing.

## Validation and overrides

Only `ISOLATION_DIRECTION`, `NUMERALS`, and `LANGUAGE_SWITCHER_LABELS` have strict
choice validation; invalid values raise `ImproperlyConfigured` when accessed.
Use real booleans for switches: the string `"False"` is truthy. Unknown keys are
ignored and reported by [system check `rtl_admin.W002`](system-checks.md).

Python callers can read `rtl_settings.CURRENCY` or `rtl_settings["CURRENCY"]`
after importing `rtl_settings` from `django_rtl_admin`. Values are cached lazily.
Django's `override_settings` resets the singleton cache when `RTL_ADMIN`,
`LANGUAGES`, or `LANGUAGE_CODE` changes; mutating a dictionary in place does not.
