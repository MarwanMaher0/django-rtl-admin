# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[semantic versioning](https://semver.org/).

## [Unreleased]

### Added

- Isolate object names on the delete confirmation page and in the delete
  success message, and isolate add/change success-message links in
  `rtl-admin.css` (`ul.messagelist a`).

## [0.1.0] - 2026-09-15

First release.

Supported on Python 3.10+ and Django 4.2, 5.x and 6.x. CI covers Python 3.10
and 3.12 against Django 4.2 and 5.2, and Python 3.12 and 3.13 against Django
6.1, each with and without Babel installed.

### Added

- **Direction-aware admin styling.** A template override of
  `admin/base_site.html` plus a stylesheet that restates the contrib admin's
  physical spacing with CSS logical properties, so the whole interface flips
  correctly in an RTL locale. Covers the navigation sidebar, the changelist,
  the filter column, the object-tools bar, the action bar, the paginator,
  aligned forms, inlines, the date/time widgets, the many-to-many selector,
  select2 autocompletes and the login page.
- **Bidirectional text safety.** `isolate()`, `isolate_runs()`,
  `mark_isolated()`, `mark_isolated_runs()`, `strip_isolates()`,
  `text_direction()` and `has_mixed_direction()`, plus the `bidi_isolate`,
  `bidi_runs`, `bidi_strip` and `bidi_dir` template filters.
- **`BidiSafeAdminMixin`**, which isolates every changelist cell while keeping
  column labels, sort links, CSS classes and change-form links intact.
- **Locale-aware formatting.** `numbering_system()`, `transliterate_digits()`,
  `format_number()`, `format_currency()`, `format_percent()`, `format_date()`,
  `format_datetime()` and `format_time()`, built on Babel when it is installed
  and on `django.utils.formats` when it is not, plus the matching `l10n_*` and
  `local_digits` template filters.
- **A language switcher** in the admin header and on the login page, posting to
  `set_language` and preserving the current admin URL.
- **An `RTL_ADMIN` settings namespace** with thirteen opt-out keys.
- **Four system checks** covering app ordering, unknown settings keys, the
  `set_language` route and `LocaleMiddleware`.
- Compiled translations for Arabic, Hebrew, Persian and Urdu.
- An example project under `example/`.

[0.1.0]: https://github.com/MarwanMaher0/django-rtl-admin/releases/tag/v0.1.0
