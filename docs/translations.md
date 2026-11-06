---
title: Translations and locales | django-rtl-admin
description: Explore shipped Arabic, Hebrew, Persian, and Urdu catalogs, RTL language recognition, demo language choices, and the locale contribution workflow.
---

# Translations and contributing a locale

Package translations, RTL recognition, and the languages offered by a project are
separate concerns. This page describes each one, then gives commands for
contributors to run locally. The commands are instructions, not a record of
extraction, compilation, or commits performed for this documentation.

## Shipped catalogs and recognized languages

The package ships four translation catalogs under
`src/django_rtl_admin/locale/`. Each directory contains both the editable
`django.po` and compiled `django.mo`:

| Language | Catalog directory | Translation of `Language` |
| --- | --- | --- |
| Arabic (`ar`) | `ar/LC_MESSAGES/` | `اللغة` |
| Hebrew (`he`) | `he/LC_MESSAGES/` | `שפה` |
| Persian (`fa`) | `fa/LC_MESSAGES/` | `زبان` |
| Urdu (`ur`) | `ur/LC_MESSAGES/` | `زبان` |

Each currently contains two non-header messages: `Language`, used by the switcher,
and `Bilingual / RTL admin`, the application's verbose name. English is the source
language, not a separate shipped `en` catalog. There is no separate `ar_EG`
package catalog.

The templates also mark `Go`, `Django site admin`, and `Django administration` for
translation, but those messages are absent from the four package catalogs.
Django's own catalogs may supply them; absence here does not establish an
untranslated runtime label. Refreshing messages can extract more than the two
currently translated strings. There is no package `djangojs` catalog and the
switcher JavaScript contains no translated strings.

RTL recognition is broader than these four translations. The direction helpers
use Django's language metadata, regional base-language fallback, and
`EXTRA_RTL_LANGUAGES`. Adding a catalog does not itself register a language as RTL,
and adding an RTL code does not install translations or add a menu entry. See
[Configuration](configuration.md).

The example project's `LANGUAGES` contains `en`, `ar`, and `ar-eg`. Hebrew,
Persian, and Urdu catalogs ship but are not enabled in that demo menu. Numbering-system
support is separate again: plain `ar` normally uses Latin digits, `ar-eg` uses
Arabic-Indic digits, and `fa` uses extended Arabic-Indic digits in the explicit
formatting helpers.

## Contributor prerequisites

Use Python 3.10 or newer and a Django release compatible with that interpreter.
For normal package installation, see [Installation](installation.md). To edit
translations, work from a repository checkout and install it in a virtual
environment. Starting at the repository root on a POSIX shell:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[test]" ruff
```

The `test` extra already installs Babel for formatting tests. Babel is optional
at runtime and is not the translation extractor or compiler. Django's
translation commands require **GNU gettext 0.19 or newer**, with `xgettext`,
`msgmerge`, `msguniq`, and `msgfmt` on `PATH`. Installing the Python package alone
does not install those system executables.

On Debian or Ubuntu:

```sh
sudo apt-get update
sudo apt-get install gettext
```

On macOS with Homebrew:

```sh
brew install gettext
export PATH="$(brew --prefix gettext)/bin:$PATH"
```

On other systems, install GNU gettext using the platform's package manager and
make its binaries available to the shell. With the contributor environment
active, check the tools before extracting messages:

```sh
django-admin --version
xgettext --version
msgmerge --version
msguniq --version
msgfmt --version
```

## Refresh an existing package locale

Run package translation commands from **`src/django_rtl_admin`**, not from
`example/`. Starting at the repository root:

```sh
cd src/django_rtl_admin
django-admin makemessages -l ar
```

This scans the package's Python and templates and updates
`locale/ar/LC_MESSAGES/django.po`. Keeping this working directory avoids mixing
the example library's model and field messages into the package catalog.

Edit the generated `.po` file:

1. Translate new or changed messages and review the existing entries.
2. Preserve message IDs, interpolation placeholders, and any markup that must
   remain intact.
3. Review the language, encoding, translator, and plural-form metadata as
   applicable. Use UTF-8 and the correct gettext locale identity.
4. Review fuzzy entries and remove the fuzzy flag only after confirming the
   translation. Fuzzy messages are not compiled by default.

Still in `src/django_rtl_admin`, compile the reviewed catalog:

```sh
django-admin compilemessages -l ar
```

The output is `locale/ar/LC_MESSAGES/django.mo`. Substitute `he`, `fa`, or `ur`
for another existing locale. Review the diff and include **both `.po` and `.mo`**
in your contribution; do not edit the binary `.mo` directly.

## Add a new package locale

From the same `src/django_rtl_admin` working directory, for example:

```sh
django-admin makemessages -l ckb
```

Translate the generated `locale/ckb/LC_MESSAGES/django.po` and review its metadata
and fuzzy entries as above. Then compile it:

```sh
django-admin compilemessages -l ckb
```

Include the new source and compiled catalogs in your contribution. A regional
gettext locale uses a name such as `ar_EG`, whereas Django's language setting uses
`ar-eg`. Only create a regional catalog when a distinct translation is needed;
selecting `ar-eg` does not require duplicating the existing Arabic catalog.

To refresh all existing catalogs, or compile all catalogs after review, run these
from `src/django_rtl_admin`:

```sh
django-admin makemessages -a
django-admin compilemessages
```

Use a locale-specific command for a focused translation contribution. Review any
changes to other catalogs before including them. There is no package-specific
translation management command; these are Django's standard commands.

## Offer the language in a Django project

Configure the available languages independently of the catalog files. Merge an
appropriate list into your project's settings, for example:

```python
USE_I18N = True
LANGUAGE_CODE = "en"
LANGUAGES = [
    ("en", "English"),
    ("ar", "Arabic"),
    ("ar-eg", "Arabic (Egypt)"),
    ("he", "Hebrew"),
    ("fa", "Persian"),
    ("ur", "Urdu"),
]
```

Follow [Quick start](quick-start.md) for app ordering, `LocaleMiddleware` after
sessions and before common middleware, and the standard `set_language` endpoint.
Keep `USE_I18N=True`. With the package app installed, Django can discover its
compiled catalogs; project-specific model labels and help text belong in your
own application's catalogs, not necessarily this package's catalog.

By default the switcher offers `LANGUAGES`. You can restrict the menu or display
both native and configured labels through existing `RTL_ADMIN` settings:

```python
RTL_ADMIN = {
    "LANGUAGE_SWITCHER_LANGUAGES": ["en", "ar-eg", "fa"],
    "LANGUAGE_SWITCHER_LABELS": "both",
}
```

Merge these keys with any other package settings. A menu override does not enable
languages outside Django's configured language support or install translations.
Keep offered languages in `LANGUAGES`. Native labels normally come from Django's
language metadata, not the two package messages. See
[Configuration](configuration.md#language-switcher) for label modes and
[Template tags and filters](template-tags.md) for custom switcher integration.

For a code Django does not recognize as RTL, consult
[Configuration](configuration.md#styling-and-direction) before adding
`EXTRA_RTL_LANGUAGES`. Only use that setting when the intended script is actually
RTL; catalog creation and numbering-system selection are not evidence of text
direction.

## Manual locale checks

Compile the catalog before testing and restart a running development server if
it has already loaded translations. For the repository demo, add the locale to
`example/config/settings.py` for your local check; its default menu does not
include Persian or Urdu. Starting at the repository root with the contributor
environment active:

```sh
cd example
python manage.py migrate
python manage.py demodata
python manage.py check
python manage.py runserver
```

Use the local demo account `demo` / `demo12345` at `/admin/`; these are demo-only
credentials. The package has no separate translation demo command.

Check the following in the language under review and again in English:

- The login and authenticated switchers list the intended language, mark it
  selected, and display the expected native/configured name.
- Switching language preserves the admin path and query string where applicable,
  and the selection persists on a subsequent request through Django's language
  cookie and middleware.
- With JavaScript disabled, the switcher submit button remains usable. With
  JavaScript enabled, changing the selection submits the form.
- The switcher's `Language` label is translated. Check `Go` and stock admin text
  too, remembering that Django can supply translations for shared messages.
- The interface direction, icon gaps, label punctuation, help text, and long
  content are readable at desktop and narrow widths. Inspect an actual change
  form as well as the changelist.
- Explicitly isolated identifiers remain readable; ordinary text, numeric-only
  values, and mixed-script prose need separate checks. See
  [BidiSafeAdminMixin](admin-mixin.md) for opt-in display handling.
- Explicit formatting helpers use the intended digit shapes and currency/date
  patterns. Do not expect the locale selection to convert every admin number.
  Babel and non-Babel output can differ; see [the Python API](api.md).

Record the Django version, browser, locale code, Babel availability, and affected
page when reporting a layout issue. The existing English/Arabic screenshots are
overviews, not stock-before comparisons or coverage for every locale. See
[Stock admin RTL defects](rtl-defects.md) for the source-level scope and known
limitations.

## Contribution checks

From the repository root, with the contributor environment active:

```sh
pytest
ruff check .
```

The repository's `CONTRIBUTING.md` also documents an optional fallback test in a
disposable contributor environment. This temporarily removes Babel and then
reinstalls it:

```sh
python -m pip uninstall -y Babel
pytest
python -m pip install "Babel>=2.12"
```

For a focused locale contribution, review both catalog files, include them in the
same pull request, and describe the manual checks performed. Add user-visible
changes under `## [Unreleased]` in `CHANGELOG.md`, keep unrelated generated changes
out of the contribution, and follow the repository's PR checklist. Commit both
the `.po` and `.mo`; compilation is not a substitute for reviewing the translated
text.

## Building the documentation

From the repository root, install the documentation extra and run the same
strict build used by CI:

```sh
python -m pip install -e ".[docs]"
mkdocs build --strict
```

The generated site is written to `site/`, which is ignored by Git. To preview
changes locally with automatic reload:

```sh
mkdocs serve
```

MkDocs Material provides navigation and search. The language selector switches
between English and Arabic; Home and Quick start are translated, while missing
Arabic pages fall back to English. Check that the Arabic pages render with
`lang="ar"` and `dir="rtl"` and that the code samples remain readable.

Python API documentation is generated from `src/` with mkdocstrings. The
Changelog page includes the repository's canonical `CHANGELOG.md` at build time;
update that file rather than duplicating release notes in `docs/changelog.md`.
Read the Docs uses `.readthedocs.yaml` to install the package's `docs` extra on
Ubuntu 24.04 with Python 3.12 and build `mkdocs.yml`, failing on warnings.

## Translating the documentation into Arabic

Documentation translation is separate from Django's gettext catalogs. The docs
site uses suffix-based localization: an Arabic version of `quick-start.md` is
`quick-start.ar.md`. The existing Arabic home and quick-start pages demonstrate
the convention.

To translate another page:

1. Keep the English canonical page and create its sibling with the `.ar.md`
   suffix, for example `translations.ar.md` alongside `translations.md`.
2. Translate prose, headings, captions, and useful alt text. Keep Python names,
   setting keys, locale codes, and runnable commands accurate rather than
   translating identifiers.
3. Link to canonical page names such as `[الإعدادات](configuration.md)` and
   `[البدء السريع](quick-start.md)`, not language-prefixed output URLs or
   `.ar.md` targets. The docs localization plugin resolves language variants.
4. Reuse screenshot filenames where appropriate and retain honest captions about
   their language and coverage. Translate captions without changing what the
   image establishes.
5. Review the Arabic rendering, links, and heading anchors in the docs preview
   before submitting. Check fragment links when translated headings change.

Markdown documentation does not go through `makemessages` or `compilemessages`.
Changing a docs page does not add a Django runtime locale, and adding a `.po`
catalog does not translate the documentation site.
