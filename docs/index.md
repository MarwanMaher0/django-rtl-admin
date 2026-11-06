---
template: home.html
title: Django admin, fluent in both directions | django-rtl-admin
description: Make Django's stock admin properly bilingual with logical RTL styling, Unicode bidi isolation, locale-aware formatting, and a language switcher.
---
# django-rtl-admin

**A properly bilingual Django admin, without replacing Django's admin.**

Django can translate its admin into Arabic, Hebrew, Persian, and other
right-to-left languages. Translating labels and flipping the page direction is
not enough: physical left/right spacing, mixed-script identifiers, and
locale-specific digits need their own handling.

`django-rtl-admin` adds direction-aware styling, bidirectional-text helpers,
locale-aware formatting, and a language switcher to the stock admin. It supports
Python 3.10+ and Django 4.2+ on compatible Python/Django combinations.

[Install the package](installation.md) · [Quick start](quick-start.md) · [Live demo and deployment](deployment.md)

Use the language selector to read Home and Quick start in Arabic.

## What it fixes

- **Layout that only partly mirrors.** Logical CSS properties address remaining
  physical spacing in object tools, action controls, aligned help text,
  date/time inputs, inline icons, and other stock-admin elements.
- **Mixed-direction text that is hard to read.** Unicode isolates and CSS bidi
  rules keep values from disturbing their surroundings. Use explicit LTR
  isolation for identifiers and run-level isolation for Latin fragments or
  punctuated numbers inside RTL prose.
- **Numbers that ignore the locale's digit system.** Opt-in formatting helpers
  support Latin, Arabic-Indic, and Eastern Arabic-Indic digits, with Babel for
  CLDR patterns and Django formatting as a fallback.
- **No built-in admin language selector.** A switcher in the header and on the
  login page posts to Django's `set_language` view and preserves the current URL.

See [Stock admin RTL defects](rtl-defects.md) for the before/after behavior and
which fixes are automatic versus opt-in. The package changes presentation, not
stored values, database schema, or the meaning of identifiers.

## The same admin in two directions

These are the existing project screenshots of the enhanced admin in English and
Arabic, **not** a stock-versus-patched comparison.

### English — left to right

![English Django admin with the package enabled, showing a left-to-right changelist](admin-en.png)

### Arabic — right to left

![Arabic Django admin with the package enabled, showing a right-to-left changelist](admin-ar.png)

## Start small

```sh
python -m pip install "django-rtl-admin[babel]"
```

Put `django_rtl_admin` before `django.contrib.admin`, configure
`LocaleMiddleware`, and include Django's i18n URLs. The [Quick start](quick-start.md)
walks through the complete setup. Babel is optional; the base package works
without it.

CSS and the switcher integrate through the package's admin template override.
For Unicode isolation of changelist values, explicitly add
[BidiSafeAdminMixin](admin-mixin.md) to your admins. Use
[template filters](template-tags.md) or the [Python API](api.md) where you need
locale-aware output; ordinary admin columns are not automatically reformatted.

## Find a reference

- [Configuration](configuration.md): all 13 `RTL_ADMIN` settings, defaults, and effects.
- [Template tags and filters](template-tags.md): the complete `rtl_admin` library.
- [System checks](system-checks.md): resolve `rtl_admin.W001`–`rtl_admin.W004`.
- [Translations and contributing a locale](translations.md): shipped catalogs,
  translation workflow, and building these docs.
- [Changelog](changelog.md): release history included from the repository's
  canonical `CHANGELOG.md`.
