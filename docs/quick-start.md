# Quick start

Start with an existing Django project whose stock admin works, then follow
[Installation](installation.md). These snippets modify that project's settings;
keep its database, security, templates, and other application configuration.

## 1. Enable request-language selection

Keep `django_rtl_admin` before `django.contrib.admin` in `INSTALLED_APPS`. In
`settings.py`, enable internationalization and choose the languages you offer:

```python
USE_I18N = True
LANGUAGE_CODE = "en"
LANGUAGES = [
    ("en", "English"),
    ("ar", "Arabic"),
    ("ar-eg", "Arabic (Egypt)"),
    ("he", "Hebrew"),
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
```

Place `LocaleMiddleware` after `SessionMiddleware` and before `CommonMiddleware`.
Retain the standard request, auth, and messages template context processors from
Django's project template. The switcher uses the request to preserve your current
admin path and query string.

## 2. Add Django's language endpoint

In your root `urls.py`:

```python
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),
]
```

The switcher posts with CSRF protection to the `set_language` URL. Django sets
the language cookie; `LocaleMiddleware` applies that selection to later
requests. If you use `i18n_patterns`, keep the `i18n/` endpoint outside that
language-prefixed group.

## 3. Check the interface

```sh
python manage.py check
python manage.py runserver
```

Open `/admin/`. Choose Arabic in the header switcher; a switcher is also available
on the login page. The admin direction and logical spacing follow the active
language. Choose English again to verify the LTR layout.

No `RTL_ADMIN` dictionary is required. For example, to show bilingual language
labels and use Egyptian pounds when no currency is specified:

```python
RTL_ADMIN = {
    "CURRENCY": "EGP",
    "LANGUAGE_SWITCHER_LABELS": "both",
}
```

## 4. Protect changelist values

The stylesheet does not rewrite your model values. Opt in to cell isolation on
each admin that displays mixed-direction text:

```python
from django.contrib import admin

from django_rtl_admin import BidiSafeAdminMixin

from .models import Book


@admin.register(Book)
class BookAdmin(BidiSafeAdminMixin, admin.ModelAdmin):
    list_display = ("title", "isbn")
    bidi_isolate_fields = ("isbn",)
    bidi_isolation_direction = "ltr"
```

This example assumes your `Book` model has `title` and `isbn` fields. The mixin
must precede `ModelAdmin`. Here it isolates only the ISBN and forces that value
to read left-to-right. Omit both attributes to isolate all eligible columns with
the configured default direction. See
[BidiSafeAdminMixin](admin-mixin.md) for exclusions and opt-outs.

## 5. Format custom output

In a custom template, load `rtl_admin`:

```django
{% load rtl_admin %}
<p>{{ book.isbn|bidi_isolate:"ltr" }}</p>
<p>{{ book.title|bidi_runs }}</p>
<p>{{ amount|l10n_number:2 }}</p>
<p>{{ amount|l10n_currency:"EGP" }}</p>
```

`amount` must be numeric for these formatting examples. These filters are
explicit opt-ins; installing the package does not automatically localize every
admin field. Plain `ar` normally uses Latin digits, while `ar-eg` uses
Arabic-Indic digits. See [Configuration](configuration.md) to force a numbering
system and [Template tags and filters](template-tags.md) for the full library.
