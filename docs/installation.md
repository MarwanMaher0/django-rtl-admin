# Installation

## Requirements

- Python 3.10 or newer.
- Django 4.2 or newer, using a Python version supported by that Django release.
- Django's stock `django.contrib.admin`, its usual dependencies, and static-file
  serving. This package extends the contrib admin; it is not a replacement admin
  theme or a database migration.

The test matrix covers supported combinations of Python 3.10–3.14 and Django
4.2, 5.0, 5.1, 5.2, 6.0, and 6.1. Not every Django release supports every Python
version.

## Install the package

```sh
python -m pip install django-rtl-admin
```

For CLDR-aware number, currency, date, and time formatting, install Babel too:

```sh
python -m pip install "django-rtl-admin[babel]"
```

Babel is optional. Without it, formatting falls back to Django's locale formats
plus digit transliteration; currency and percentage output is simpler. See the
[Python API](api.md#locale-aware-formatting) for fallback differences.

## Register the app before the admin

In your project's `settings.py`, insert `django_rtl_admin` **before**
`django.contrib.admin` in the existing `INSTALLED_APPS` list. Keep your other apps:

```python
INSTALLED_APPS = [
    "django_rtl_admin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]
```

Use Django's app template loader (`APP_DIRS=True` in a standard DjangoTemplates
configuration). App order lets the package's `admin/base_site.html` override the
stock template. It loads the package stylesheet and language-switcher script;
there is no CSS or JavaScript build step.

## Static files and deployment

The wheel includes templates, CSS, JavaScript, and compiled translation catalogs.
Use your project's normal deployment process:

```sh
python manage.py collectstatic --noinput
python manage.py check
```

Serve the collected static files as you normally would for Django admin. The
package itself has no models or migrations. A newly created Django project still
needs Django's own migrations and a staff/superuser account.

Continue with [Quick start](quick-start.md) to configure request languages and
the switcher endpoint. See [System checks](system-checks.md) if setup emits a
`rtl_admin.W001`–`rtl_admin.W004` warning.

## Existing template overrides and themes

A project-level `templates/admin/base_site.html` takes priority over app
templates. If you maintain your own override, extend the package's explicit base
and retain parent blocks:

```django
{% extends "django_rtl_admin/base_site.html" %}

{% block title %}Library admin | {{ block.super }}{% endblock %}
```

The package adds body classes in `bodyclass`, loads assets in `responsive`, and
places switchers in `userlinks` and anonymous `branding`. Preserve
`{{ block.super }}` when overriding these blocks to retain those features.
Third-party admin themes may use different markup or template inheritance;
compatibility with them is not guaranteed by the stock-admin stylesheet.
