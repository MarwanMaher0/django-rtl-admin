# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[semantic versioning](https://semver.org/).

## [Unreleased]

### Added

- **Type information.** The package now ships a `py.typed` marker
  ([PEP 561](https://peps.python.org/pep-0561/)), so type checkers read its
  annotations in your project. Every public function in `bidi`, `formatting`,
  `conf`, `mixins` and the `rtl_admin` template tags is fully annotated, the
  `RTL_ADMIN` keys read through `rtl_settings` have declared types, and
  `BidiSafeAdminMixin` type-checks when mixed into `admin.ModelAdmin`. The
  source passes `mypy --strict` with django-stubs: `nox -s typecheck` runs it,
  and CI runs that session on every push. No runtime behaviour changes.
- System checks now report `rtl_admin.E001` for invalid setting choices and
  `rtl_admin.W005` for invalid configuration types, reading raw settings without
  triggering runtime `ImproperlyConfigured`; runtime validation remains in place.
- **Full test matrix.** `noxfile.py` defines a test cell for every
  Python/Django pair Django supports — Python 3.10 to 3.14 against Django 4.2,
  5.0, 5.1, 5.2, 6.0 and 6.1 — plus a no-Babel cell, each run under coverage.
  CI reads the cells from the noxfile and runs them all, prints the coverage
  table in each job summary, publishes one cell's report to Coveralls, and the
  README carries the coverage badge. Python 3.14 is now declared in the
  classifiers.
- **Release workflow.** `.github/workflows/release.yml` builds the sdist and
  wheel once, checks them with `twine check`, and publishes that same build
  to PyPI with trusted publishing (OIDC, no API tokens) when a `v*` tag is
  pushed. Running the workflow by hand publishes to TestPyPI instead, so a
  release can be rehearsed first. The build fails if the tag does not match
  the version in `pyproject.toml`. The one-time setup and the release steps
  are in `CONTRIBUTING.md`.
- **Browser tests.** `tests/e2e/` drives a real Chromium through Playwright
  against the admin in Arabic (RTL) and English (LTR), in the light and dark
  schemes, at 360px and 1280px: login, the changelist (search, filters,
  actions, pagination), the change form (fieldsets, collapse, help text,
  validation errors), tabular and stacked inlines, the calendar and clock
  popups and the autocomplete. Every page is checked for horizontal overflow,
  for icons and arrows pointing the right way and for mirrored layout, and a
  screenshot is saved to `test-artifacts/e2e/`. Run them with `nox -s e2e`;
  CI runs them on the newest Python/Django pair only and uploads the
  screenshots as a build artifact.
- **Automated accessibility checks.** The browser suite also runs axe-core
  against the changelist, change form and delete confirmation in Arabic and
  English, in light and dark schemes and at both viewport widths. It checks
  WCAG 2 A/AA, 2.1 AA and 2.2 AA rules and saves a JSON report for each
  failing scan.
- **Complete translation catalogs.** The package now ships six locales —
  Arabic (`ar`), Kurdish Sorani (`ckb`), Hebrew (`he`), Persian (`fa`),
  Uyghur (`ug`) and Urdu (`ur`) — and every catalog translates the full
  message set: the switcher labels, the app's verbose name, the changelist
  sorting and action labels and the inline row labels. Messages shared with
  Django's admin mirror the wording of Django's own admin catalog for the
  same language, so overridden and stock templates render identically;
  entries written without a native reviewer carry a `TRANSLATORS` note in
  the `.po` asking for corrections.
- **Translation integrity tests.** `tests/test_translations.py` extracts the
  marked messages from the package's Python and templates, asserts every
  shipped locale translates all of them with intact placeholders and no fuzzy
  flags, and verifies each committed `.mo` matches its `.po` and is
  reproduced by recompiling it (Babel or `msgfmt`, skipped when neither is
  installed). The packaging test and the CI wheel check now require the
  compiled catalogs of all six locales.

### Fixed

- `FONT_STACK` with a quoted family no longer breaks the override.
  `rtl_admin_styles` used to HTML-escape the value inside `<style>`, where
  entities are not decoded, so `'"Noto Naskh Arabic", serif'` reached the
  browser as `&quot;Noto Naskh Arabic&quot;` and the rule was dropped. The
  stack is now serialized as CSS: a string is read as a `font-family` list,
  each sequence entry is one family name, family names become CSS strings with
  `\` and `"` escaped, pre-quoted names are accepted, and generic keywords
  (`serif`, `system-ui`, ...) plus `-apple-system` and `BlinkMacSystemFont`
  stay bare. A malformed value, or one containing `<`, `>`, `{`, `}`, `;` or a
  control character, is skipped with a warning on the `django_rtl_admin`
  logger and the shipped stack applies. A sequence entry containing a comma is
  now one family name rather than a list.
- Direction detection now follows `settings.LANGUAGES_BIDI` exactly as Django's
  `get_language_bidi()` does -- the base subtag against the raw entries -- with
  `EXTRA_RTL_LANGUAGES` as the additive escape hatch. The per-language `bidi`
  flag in `LANG_INFO` is no longer consulted, so for codes in `LANGUAGES_BIDI`
  the body class agrees with the document's `dir` attribute. `EXTRA_RTL_LANGUAGES`
  codes can still turn the body RTL without the document, and the new
  `rtl_admin.W006` check warns about exactly that when a code is missing from
  `LANGUAGES_BIDI`, where Django reads the document direction.
- The `l10n_*` and `local_digits` filters now fail silently like Django's
  built-ins: numeric filters accept and normalize finite numeric strings,
  including exponent notation and surrounding whitespace, and return invalid
  values as text. Non-finite values are rejected instead of formatted, an invalid `l10n_number` precision argument is
  ignored, and invalid dates or times—including integer timestamps—render
  empty. The Python `format_currency()` helper validates its input and raises
  `ValueError` for nonempty, nonnumeric, or non-finite values instead of
  rendering malformed amounts.
- `rtl_admin.W001` now uses ordered app-registry names to recognize custom
  AppConfig subclasses, including project-defined admin configurations.
- `format_datetime()`, `format_time()`, `l10n_datetime` and `l10n_time` now
  convert aware `datetime` values to Django's active time zone (`TIME_ZONE` or
  `timezone.override()`) with `django.utils.timezone.localtime()` on both the
  Babel and Django fallback paths, and register `l10n_datetime` and `l10n_time`
  with `expects_localtime=True`; naive `datetime`/`time` values and plain
  `date` values are left untouched.
- On Django 5.1+ `BidiSafeAdminMixin` no longer drops sorting for related
  lookups such as `publisher__name` in `list_display`: the lookup is resolved
  with `get_fields_from_path()`, used as the column's `admin_order_field`, and
  the final field's display value is isolated (a lookup ending in a
  `BooleanField` is left alone). Django 4.2/5.0 behaviour is unchanged.
- Three stylesheet rules scoped `dashboard` and `change-list` as descendants of
  `.rtl-admin`, but stock templates put those classes on the same `<body>`, so
  the rules never matched. They are compound selectors now. Dashboard action
  links restate the stock spacing logically (16px of icon room at inline-start,
  the stock 0.6em gap at inline-end, dropped below 1024px like the stock
  responsive sheets); filtered changelists restate the stock border resets and
  mirror `changelists.css`'s unmirrored `padding-right: 1em` header-cell
  widening to the logical end while keeping the stock padding at the start —
  8px, or the 10px `responsive.css` applies at or below 1024px.
  The browser suite verifies the rendered geometry in both languages, both
  colour schemes and at both viewport widths.

Defects found by the browser tests:

- Accessibility checks now cover and fix missing names and labels on the
  language switcher, action checkboxes, tabular-inline controls and split
  date/time inputs; disabled mobile zoom; insufficient color contrast; links
  distinguished only by color; and undersized filter, pagination and related
  object link targets. These fixes include older Django releases whose stock
  admin predates the equivalent upstream accessibility improvements.

- The navigation sidebar's collapse toggle pointed the wrong way in RTL: the
  stylesheet swapped the `«`/`»` characters the browser already mirrors.
- A collapsed changelist filter showed `→`, pointing away from its content,
  in RTL; it now shows `←` (and `↓` when open).
- On Django 6.1 help text and error lists in aligned forms were indented by
  the old label column, leaving them detached from their field in both
  directions.
- The calendar's previous/next arrows were restated with Django 6.1's sprite
  offsets, which showed the wrong slices on Django 4.2; contrib's own RTL
  swap is now left in charge.
- Tabular inline rows with an existing object were padded so their object
  label overlapped the inputs below it.
- The "Add another" inline link kept its icon on the left in RTL on Django
  4.2/5.0, and on phones the icon overlapped the link text in both
  directions.
- Between 768px and 1024px the side column (`#content-related`, e.g. the
  dashboard's "Recent actions") kept its full-width margins and overflowed
  the page; on phones it now stacks at full width.
- On phones the RTL calendar and clock popups were pinned off-screen instead
  of being centred.
- On phones a stacked inline's labels and long text inputs were wider than the
  inline and were clipped: the end of each label in English, the start of
  each label and input in Arabic, where the first characters typed were
  hidden. Rows, labels and controls now size to the inline (`width: 100%`,
  `min-width: 0`, `box-sizing: border-box`). The page never scrolled, so the
  overflow check missed it; the browser tests now check every inline label
  and control against the viewport.
- On phones a tabular inline's text inputs kept their 20em width and pushed
  the table, and the delete checkbox, off-screen; they now share the row.
- On Django 6.0 phones the split date/time fields of a form or stacked inline
  collapsed to nothing beside their floated legend.
- On Django 4.2–5.2 the icon of a success, warning or error message (after a
  save, a delete or an admin action) stayed on the left of RTL text; the
  message list is now mirrored at every width.
- Form labels and fieldset legends followed the direction of their own text,
  so an untranslated English label sat on the wrong side of an Arabic form;
  they now align with the form, while legends still isolate their text.

### Changed

- Packaging prepared for PyPI: the licence is declared as the SPDX expression
  `MIT` (PEP 639), the project URLs include Documentation, Changelog and
  Issues, README images use absolute URLs so they render on PyPI, and the
  install instructions use `pip install django-rtl-admin`.

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
