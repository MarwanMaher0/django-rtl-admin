# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[semantic versioning](https://semver.org/).

## [Unreleased]

### Added

- Umm al-Qura Hijri calendar support without a new runtime dependency.
  `to_hijri()` converts a Gregorian `date` or `datetime` to a frozen
  `HijriDate` (`year`, `month`, `day`, `month_length`) and `from_hijri()` goes
  back, using the official table for 1343–1500 AH (1924-08-01–2077-11-16 CE);
  values outside that range raise `ValueError`. `format_hijri_date()` renders
  full Arabic, Persian, or Urdu month names (English transliteration
  elsewhere), follows `NUMERALS`/`numbering_system()` and
  `transliterate_digits()` for digits, supports `long`, `medium`, and `short`
  formats, and appends the Hijri era suffix unless `suffix=False`. The
  `{{ value|hijri_date }}` template filter is available from
  `{% load rtl_admin %}`.
- **CSV export admin actions.** New `django_rtl_admin.actions` module with
  `export_as_csv`, a Django admin action usable on any `ModelAdmin`
  (`BidiSafeAdminMixin` is not required), and the
  `make_csv_export_action(fields=None, *, filename=None, digits="latn",
  header="verbose", bom=True, delimiter=",")` factory, both exported from the
  package root. The action exports only the selected rows in `list_display`
  order (callables, admin methods, properties and related `field__subfield`
  lookups included, the latter resolved on every supported Django) with
  translated `short_description`/verbose-name headers, writes UTF-8 with a BOM
  so Excel detects the encoding, strips Unicode bidi control characters,
  converts Arabic-Indic and Persian digits via `transliterate_digits()`
  (`"latn"` or the active locale's `"native"` system) while keeping ISO 8601
  date/datetime/time cells in ASCII, formats dates and datetimes as ISO 8601 in
  the current time zone, neutralises spreadsheet formula injection with a
  leading apostrophe, streams through `StreamingHttpResponse` and
  `QuerySet.iterator()` so 50,000-row exports never load into memory at once,
  and sends an RFC 6266 encoded `Content-Disposition` filename
  (`filename*=UTF-8`) so Arabic model names survive. The label is translated
  and the action is decorated with `admin.action(permissions=["view"])`, so the
  admin only offers it to users with the view permission and invoking it
  otherwise raises `PermissionDenied`. Each factory action gets a distinct
  `__name__` derived from its options, so several can share one `ModelAdmin`.
- `BidiSafeAdminMixin` can sort selected text columns by folded Arabic spelling,
  for ascending and descending header sorts and `ModelAdmin.ordering`. Opt in
  with `bidi_arabic_ordering` or disable it globally with
  `RTL_ADMIN["ARABIC_ORDERING"] = False`. Use `arabic_sort_key()` in Python and
  `arabic_sort_expression()` in querysets without changing stored text.
- **Direction-aware print stylesheet (`django_rtl_admin/css/print.css`).**
  Loaded with `media="print"` from `django_rtl_admin/base_site.html` right
  after `rtl_admin_styles` and controlled by the new boolean setting
  `RTL_ADMIN["PRINT_STYLES"]` (default `True`, validated in `conf.py` and
  covered by the generic boolean system check). Uses CSS logical properties exclusively with `@page` margins
  suitable for A4 and Letter, hides the navigation sidebar, header and header
  tools, breadcrumbs, object-tools buttons, changelist action bar and selection
  checkboxes, filters, search bar, paginator controls, submit rows and inline
  add/delete controls, and keeps the page title, object fields, read-only
  values, inline tables and changelist results with repeating table headers
  (`thead { display: table-header-group; }`), unbroken rows and fieldsets,
  wrapped Arabic and mixed-direction text, readable links without printed URLs,
  screen-matching RTL/LTR column order and preserved `unicode-bidi` cell
  isolation.
- `BidiSafeAdminMixin` optionally localizes digits in changelist cells of
  integer, decimal, float, date, datetime, time, and duration model fields
  (including related lookups on Django 5.1+) for the active language via
  `transliterate_digits(text, numbering_system())`, keeping Django's rendered
  separators, `latn` locales, text/choice/foreign-key/callable columns, and
  `list_editable` inputs, filters, paginator, and action counter untouched.
  Enable globally with `RTL_ADMIN["LOCALIZE_CHANGELIST_DIGITS"] = True` or per
  admin with `bidi_local_digits = True`; opt one admin out with
  `bidi_local_digits = False`, and `RTL_ADMIN["NUMERALS"]` forces the
  numbering system.
- `BidiSafeAdminMixin` generates blank `prepopulated_fields` slugs from
  Arabic-script titles on add forms and new inline rows, respecting the
  `SlugField` Unicode and length options without rewriting existing slugs or
  making them unique. Use `arabic_slugify()` directly, or opt out with
  `RTL_ADMIN["TRANSLITERATE_SLUGS"] = False` or `bidi_transliterate_slugs = False`
  on the admin or inline.
- `BidiSafeAdminMixin` folds equivalent Arabic letter forms, harakat, tatweel,
  and digits in changelist and autocomplete search across text `search_fields`
  while keeping ASCII and Hebrew queries untouched. Use `arabic_search_regex()`
  in custom `iregex` queries, or disable the mixin behavior with
  `RTL_ADMIN["FOLD_ARABIC_SEARCH"] = False` globally or
  `bidi_fold_search = False` on one admin.
- `BidiSafeAdminMixin` accepts Arabic-Indic and Persian digits in numeric, date,
  and time fields in any UI language, including `list_editable` and mixin-enabled
  inlines. Use `normalize_numeric_input()` in custom parsers, or disable the
  mixin behavior with `RTL_ADMIN["NORMALIZE_INPUT_DIGITS"] = False` globally or
  `bidi_normalize_input = False` on one admin.
- **Plain-text related and protected entries on delete confirmation pages are isolated.**
  When `bidi_isolation_enabled(request)` is true, `BidiSafeAdminMixin.get_deleted_objects()`
  wraps the object name in plain-text `deleted_objects` and `protected` entries with `isolate()`;
  linked entries, nesting, counts, permissions and escaping are unchanged.
- **Read-only field isolation on the change form ([#1](https://github.com/MarwanMaher0/django-rtl-admin/issues/1)).**
  `BidiSafeAdminMixin` now isolates embedded opposite-direction runs inside
  `readonly_fields` display values on the change form (and in view-only mode and
  mixin-enabled inlines) via `render_change_form` and `mark_isolated_runs()`,
  without overriding `admin/includes/fieldset.html`. Each paragraph line's first
  strong character sets the base direction (falling back to the active UI
  direction), so paths, version strings and hyphenated dates inside Arabic prose
  render in left-to-right order in both RTL and LTR admins while field labels,
  help text, CSS classes, boolean icons and `SafeString` HTML stay unchanged.
  Opt out globally with `RTL_ADMIN["ISOLATE_READONLY_FIELDS"] = False`, per
  admin with `bidi_isolate_readonly = False`, or per field/callable with
  `bidi_isolate_exclude`.
- **Object names in admin sentences are isolated ([#2](https://github.com/MarwanMaher0/django-rtl-admin/issues/2)).**
  The admin quotes an object's `__str__` in messages, headings and the delete
  page, where an identifier such as `978-0-262-03561-3` or `v1.2.3` was
  reordered in an RTL admin.
    - `BidiSafeAdminMixin` wraps the name with `isolate()` where Django prints
      it as plain text: the delete confirmation question and breadcrumb
      (`render_delete_form`), the "deleted successfully" message
      (`response_delete`) and the "added successfully" message for a user
      without change permission (`response_add`). These follow
      `RTL_ADMIN["ISOLATE_CHANGELIST"]` and `bidi_isolate_changelist`.
    - `rtl-admin.css` sets `unicode-bidi: isolate`, under the existing
      `.rtl-admin--isolate-cells` switch (`RTL_ADMIN["ISOLATE_TABLE_CELLS"]`),
      on the linked name in the "added" and "changed" messages
      (`ul.messagelist li a`), on the change-form subtitle `<h2>` (a child of
      `#content` up to Django 6.0, inside `.titles-and-tools > .titles` on 6.1)
      and on the object links in the lists of the delete and delete-selected
      confirmation pages.
    - The same CSS switch isolates dashboard Recent actions links and
      related-object labels beside `raw_id_fields`. Object history table cells
      and selected names, choice chips and dropdown options in Select2
      autocompletes get `unicode-bidi: plaintext` instead, so each value takes
      its own base direction, while their text stays aligned with the UI
      direction. Deleted names in Recent actions are bare text; CSS cannot
      isolate them individually.
    - The linked messages, popup responses, redirects and `LogEntry.object_repr`
      stay exactly as Django makes them, HTML in `__str__` stays escaped, and
      with the switch off the output matches a stock `ModelAdmin`.
    - Django 4.2 to 6.1 link the name in the "changed" message whatever the
      user's permissions, and refuse the change view without change
      permission, so that message has no plain-text form. The mixin's
      `response_change` only acts when a base class sends Django's "changed"
      message with a plain name. The history page has no subtitle.
- Computed-style browser coverage for README defects 1, 2, 3, 4, 5, 6, 8 and
  selected rules from 10, reusing the existing e2e suite at 1280px in `ar-eg`
  and `en` with package CSS enabled and disabled. All measured English computed
  properties must match stock. Explicit stock-parity cases cover already-mirrored
  sidebar chevrons, Django 6.0+ object-tools items and Django 6.1+ help padding,
  rather than claiming a negative control for every case. Defect 8 covers outer
  and inner help text and fieldset descriptions.
  ([#3](https://github.com/MarwanMaher0/django-rtl-admin/issues/3))

### Changed

- The nox/CI e2e matrix now covers Django 5.2 and the newest series (currently
  6.1) on Python 3.14, with CI deriving sessions from nox and uploading
  session-specific screenshot artifacts. `CONTRIBUTING.md` documents both
  sessions and a one-defect command; the English and Arabic RTL-defect guides
  map README numbers to tests and document version-specific stock-parity cases
  and coverage limits. ([#3](https://github.com/MarwanMaher0/django-rtl-admin/issues/3))
- The code base is formatted with `ruff format`, with no behaviour change, and
  `nox -s lint` (the CI `ruff` job) now runs `ruff format --check .` after
  `ruff check .`. The check covers the Python code blocks in the Markdown
  files, so a few README examples were reformatted too. ruff is bounded to
  `>=0.16,<0.18` in `noxfile.py` and is part of the `test` extra, and a test
  runs the same format check in every test cell.
- Every job in `ci.yml`, `docs.yml` and `release.yml` runs on `ubuntu-24.04`
  instead of `ubuntu-latest`; a test fails if a `-latest` runner comes back.
- `release.yml` calls `ci.yml` (now a reusable `workflow_call` workflow) and
  builds the sdist and wheel only after every CI job has passed, for a tag
  push and for a TestPyPI rehearsal alike. `ci.yml` no longer triggers on
  `v*` tags itself, so a release tag runs CI and the Coveralls upload once,
  inside the Release workflow, instead of twice.
- The workflow tests parse the workflow files with PyYAML instead of matching
  indentation. The nox test cells install PyYAML so the tests run in CI, and
  it is in the `test` extra so they also run with a plain `pytest` in a
  checkout.
- The README and the installation guide (English and Arabic) say that
  `collectstatic` needs `STATIC_ROOT`, in the same paragraph as the
  instruction; a test checks that paragraph.
- `CONTRIBUTING.md` documents the one-time Settings → Pages → Source: GitHub
  Actions step that the docs workflow needs, and the `ruff format` check.

### Fixed

- Without Babel, missing datetime patterns now combine the locale's regular or
  short date with its time instead of inheriting English defaults. CLDR-derived
  patterns cover Urdu and, on Django 4.2, Uyghur. Project `FORMAT_MODULE_PATH`
  overrides still take precedence. The time fallback now accepts custom Django
  format strings; named time styles still use `TIME_FORMAT`.
- **Five unmirrored form-control gaps in RTL.** `rtl-admin.css` now resets
  physical horizontal sides and restates with logical properties the 4px end
  margin on `form div.radiolist input[type="radio"]`, the 10px end padding on
  all aligned labels (`.aligned label`, now gated to `.rtl-admin--pre-6-1` with
  10px instead of `1em` so stock vertical padding and LTR parity stay intact
  before 6.1 and Django 6.1+ keeps zero padding) and on Django 6.1+ radio
  labels (`form div.radiolist label`), the 5px start padding on
  `.aligned .vCheckboxLabel` above 767px, the 10px start margin on
  `.delete-confirmation form .cancel-link` across both delete confirmation
  pages, and the `filter_vertical` chooser's 40% start margin (scoped to
  `.rtl-admin--rtl` so Django 4.2 English keeps `margin: 15px auto` below
  1024px) and 5px start item padding (`.stacked ul.selector-chooser` and
  `.stacked .selector-chooser li`, preserving the 3px responsive reset at or
  below 1024px), with computed-style coverage in `test_defect_10_unmirrored_rules`.
- **CSS parity with stock English admin ([#3](https://github.com/MarwanMaher0/django-rtl-admin/issues/3)).**
  The object-tools `li` float/margin fix, including its CSS media-query rule, is
  gated by the `rtl-admin--pre-6-0` body class. Before Django 6.0, RTL items float
  right with a 5px right margin while LTR keeps the stock left float and 5px left
  margin. Django 6.0+ (including 6.1) retains stock inline-block/no-float items in
  both languages, with zero margins on the first item. The `rtl-admin--pre-6-1`
  gate preserves stock LTR datetime left/right margins of 5px/2px before 6.1 and
  0/2px on 6.1+, with exact RTL mirrors of 2px/5px and 2px/0. Aligned help text
  keeps stock LTR padding of 10px/3px before 6.1 and mirrors it to 3px/10px in RTL;
  on 6.1+ padding remains zero on both sides in both languages. Help text (outer
  and inner elements) and fieldset descriptions now use `unicode-bidi: plaintext`
  only in RTL; English keeps stock `isolate`. Label, legend, read-only-value and
  input safety nets are unchanged. Sidebar chevrons remain stock in both states;
  the README corrects its earlier claim that their literals need swapping.

### Removed

- `docs/robots.txt`. The documentation is a GitHub Pages project site under
  `/django-rtl-admin/`, and crawlers only read `robots.txt` at the root of the
  host, so the file was never fetched. Pages keep their `robots` meta tag,
  every page now links the sitemap with `<link rel="sitemap">`, and `llms.txt`
  lists it.
- The unused `seo_en_path`, `seo_ar_path`, `seo_title_only` and
  `seo_is_landing` page metadata from the docs build hook; a test now fails if
  the hook sets a value that no template reads.

## [0.2.0] - 2026-11-12

### Added

- **Arabic documentation.** Installation, deployment, configuration, template tags,
  the admin mixin, system checks, locale contributions and stock admin RTL defects
  now have Modern Standard Arabic pages and navigation titles, with a bilingual
  glossary in the locale guide. Code examples and heading anchors match English;
  a docs build hook rejects code-block or heading-count drift. Translated pages
  use Arabic SEO metadata and reciprocal hreflang links, while the Python API
  and changelog remain English.
- **CI and packaging hygiene.** Every GitHub Action in `.github/workflows/ci.yml`
  is now pinned to a full commit SHA with a `# vX.Y.Z` version comment, matching
  `release.yml`, and `.github/dependabot.yml` opens grouped weekly pull requests
  for `github-actions` and `pip`. The sdist now ships `noxfile.py`,
  `CONTRIBUTING.md` and `SECURITY.md`, and a new CI `sdist` job builds the
  source tarball, unpacks it in a temporary directory, installs it and runs
  `pytest` (excluding `e2e`) from the unpacked archive. Coverage reporting now
  enforces `fail_under = 95` (`--fail-under=91` on the no-Babel cell).
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

- Number formatting without Babel now renders from built-in CLDR tables
  instead of Django's locale files. `format_number()`, `format_currency()` and
  `format_percent()` use each supported locale's own group and decimal
  separators — `ar-eg` shows `١٬٢٣٤٬٥٦٧٫٨٩١`, `ar-ma` shows `1.234.567,891`
  and `kk` groups with a nonbreaking space — and its grouping convention
  (Indian-style `12,34,567` for `dv` and `en-in`). Rounding matches Babel:
  half-to-even, at most three fraction digits by default with trailing zeros
  stripped, or exactly `decimal_pos` digits when given; `grouping=False` still
  drops group separators and a sign survives rounding to zero. Decimals with
  more than 28 significant digits keep every digit (Babel's quantize raises on
  those, so the fallback renderer handles them at full precision). The fallback
  numbering-system table was corrected against CLDR 46 as well: `ar-ae` and
  `dv` use Latin digits, while `ar-dj`, `ar-er`, `ar-il`, `ar-km`, `ar-mr`,
  `ar-so`, `ar-ss` and `ar-td` use Arabic-Indic digits. Locales the tables do
  not cover keep using Django's formatter. When Babel is installed, tests
  assert the two paths agree exactly.
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
- `isolate()`, `isolate_runs()`, `mark_isolated()`, `mark_isolated_runs()` and
  `strip_isolates()` (together with `bidi_isolate`, `bidi_runs`, `bidi_strip`
  and `BidiSafeAdminMixin`) now strip all twelve Unicode `Bidi_Control`
  characters — including `ALM` (`U+061C`), directional embeddings and overrides
  (`LRE`, `RLE`, `PDF`, `LRO`, `RLO`) and existing `LRI`/`RLI`/`FSI`/`PDI`
  isolates — before wrapping, so an embedded `PDI` or override cannot escape an
  isolate and reorder surrounding text. `is_isolated()` now checks that the
  string forms a balanced isolate without embedded directional overrides.
- Narrowed `nox` test runs (for example `nox -s "tests(py3.12-django5.2)" -- -k bidi`)
  now pass `--fail-under=0` to `coverage`, keeping the full-suite coverage
  threshold intact when no `posargs` are supplied.

### Changed

- Packaging prepared for PyPI: the licence is declared as the SPDX expression
  `MIT` (PEP 639), the project URLs include Documentation, Changelog and
  Issues, README images use absolute URLs so they render on PyPI, and the
  install instructions use `pip install django-rtl-admin`.
- Documentation is now built and deployed to GitHub Pages
  (`https://marwanmaher0.github.io/django-rtl-admin/`) by
  `.github/workflows/docs.yml` instead of Read the Docs.

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

[Unreleased]: https://github.com/MarwanMaher0/django-rtl-admin/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/MarwanMaher0/django-rtl-admin/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/MarwanMaher0/django-rtl-admin/releases/tag/v0.1.0
