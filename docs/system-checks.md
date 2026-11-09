---
title: System checks | django-rtl-admin
description: Diagnose rtl_admin.E001 and W001 through W005 for invalid configuration choices and types, app ordering, unknown keys, the missing set_language endpoint, and LocaleMiddleware setup.
---

# System checks

The app registers five Django check functions that can emit one error ID and
five warning IDs. Run them as part of your project's normal checks:

```sh
python manage.py check
```

E001 is a Django `Error`; W001 through W005 are Django `Warning` objects. Their
exact prefix is `rtl_admin`, not `django_rtl_admin`. Registration occurs when
`django_rtl_admin.apps.RTLAdminConfig.ready()` imports the checks module.

The two new checks read raw settings rather than the runtime configuration
accessor, so invalid configuration is reported without those checks raising
`ImproperlyConfigured`. Runtime validation remains in place.

| ID | Condition | Primary fix |
| --- | --- | --- |
| `rtl_admin.E001` | A choice setting has an unsupported value. | Use one of the accepted choices for the reported option. |
| `rtl_admin.W001` | The RTL admin app is listed after contrib admin. | Put `django_rtl_admin` before `django.contrib.admin`. |
| `rtl_admin.W002` | `RTL_ADMIN` contains unsupported keys. | Correct or remove the reported keys. |
| `rtl_admin.W003` | The switcher is enabled and `set_language` cannot be reversed. | Route Django's language endpoint or disable the switcher. |
| `rtl_admin.W004` | The switcher is enabled and the exact `LocaleMiddleware` path is absent. | Add the middleware or disable the switcher. |
| `rtl_admin.W005` | `RTL_ADMIN` is neither a mapping nor `None`, or a checked option has an invalid type. | Use a mapping or `None` and the documented option types. |

## `rtl_admin.E001`: invalid setting choices

`check_settings_values` emits a separate E001 for each invalid option in this
table:

| Setting | Accepted values |
| --- | --- |
| `ISOLATION_DIRECTION` | `"auto"`, `"ltr"`, `"rtl"` |
| `NUMERALS` | `"auto"`, `"latn"`, `"arab"`, `"arabext"` |
| `LANGUAGE_SWITCHER_LABELS` | `"native"`, `"translated"`, `"both"` |

Correct the reported value or omit the option to use its default. The check
reports invalid choices before runtime access; accessing an invalid choice at
runtime still raises `ImproperlyConfigured`.

## `rtl_admin.W001`: app order

The check uses `django.apps.apps.get_app_configs()` and reads each config's
`name` in registry order. If both `django_rtl_admin` and `django.contrib.admin`
are present, the former must appear first. If either is absent, this check is
silent.

Insert the app before contrib admin in your existing app list, retaining the
project's other apps and dependencies. This fragment illustrates the order:

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

App-template resolution follows this order so the package can shadow
`admin/base_site.html`. Both usual paths such as
`django_rtl_admin.apps.RTLAdminConfig` and custom subclasses such as
`myproject.apps.MyAdminConfig` are recognized through their registered `name`
(for example, `django.contrib.admin`), not their import path.

A clean W001 result does not prove the effective template comes from the package:
project-level templates and custom loaders can still take precedence. If you
maintain an override, extend `django_rtl_admin/base_site.html` as described in
[Installation](installation.md).

## `rtl_admin.W002`: unknown settings

The check compares the keys in `RTL_ADMIN` with the supported defaults. A single
warning lists all unknown keys in sorted order and its hint lists supported keys.
Unknown keys are ignored, so a typo does not disable or configure a feature.

For example, use `ENABLE_CSS`, not `ENABEL_CSS`:

```python
RTL_ADMIN = {
    "ENABLE_CSS": False,
}
```

See [Configuration](configuration.md) for all 13 supported settings. W002 checks
key names only; E001 reports invalid choices and W005 reports the type problems
listed below.

## `rtl_admin.W003`: missing language endpoint

When `LANGUAGE_SWITCHER` is truthy, the check calls `reverse("set_language")`.
Any ordinary exception from that call produces W003, including a missing route
or another URLconf error. The name must be available without a namespace.

Add Django's language endpoint to the root URLconf alongside your other routes:

```python
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),
]
```

If the route already exists, investigate the underlying URLconf/reversal error.
If you do not offer switching, set `RTL_ADMIN["LANGUAGE_SWITCHER"] = False`.

The switcher inclusion tag hides the form for `NoReverseMatch` only. The check
catches more exceptions, so not every W003-causing URLconf error is also hidden
at render time. Routing a name alone does not prove a custom replacement view
implements Django's language-cookie behavior.

## `rtl_admin.W004`: missing locale middleware

When `LANGUAGE_SWITCHER` is truthy, the exact string
`django.middleware.locale.LocaleMiddleware` must be in `MIDDLEWARE`. Otherwise
the check warns that the selected language will not stick.

Add it after `SessionMiddleware` and before `CommonMiddleware`, retaining the
rest of your middleware. A standard arrangement is:

```python
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

The check verifies presence, not order. A compatible custom subclass under a
different import path is not recognized. Missing middleware does not hide the
switcher form; it is a separate runtime requirement. Follow
[Quick start](quick-start.md) for the complete language-selection setup.

## `rtl_admin.W005`: invalid setting types

`check_settings_types` emits a separate W005 for each invalid type it detects:

| Setting | Type requirement |
| --- | --- |
| `RTL_ADMIN` | A `collections.abc.Mapping` (such as `dict` or `types.MappingProxyType`), or `None` to use the defaults. |
| `EXTRA_RTL_LANGUAGES` | Must not be a bare string; use a collection of language codes instead. |
| `FONT_STACK` | `None`, a string, or a sequence of strings such as a list or tuple. |
| `ENABLE_CSS`, `ISOLATE_CHANGELIST`, `ISOLATE_TABLE_CELLS`, `PLAINTEXT_FORM_FIELDS`, `USE_BABEL`, `LANGUAGE_SWITCHER` | A real `bool` (`True` or `False`), not a truthy or falsy substitute. |

For example, use `False`, not `"false"` or `0`, for a switch. Omitting
`RTL_ADMIN` or setting it to `None` uses the defaults. Mapping values are checked
normally, including unknown keys, invalid choices and language-switcher setup.
The `EXTRA_RTL_LANGUAGES` diagnostic targets bare strings, not language-code
validity. These type checks are not comprehensive validation of all
configuration contents.

## Disabling the switcher checks

If the switcher is not wanted, disable its feature rather than merely hiding
warnings:

```python
RTL_ADMIN = {
    "LANGUAGE_SWITCHER": False,
}
```

This skips both W003 and W004 and suppresses the form and its script. E001,
W001, W002, and W005 still run. W003 and W004 can occur together, and they still
run with only one configured language even though the form hides in that case.

## What a clean result does not guarantee

The checks do not validate `USE_I18N`, request/CSRF template context, custom
language-list validity, asset delivery, Babel availability, mixin attributes,
or effective template inheritance. They also do not verify middleware order.
Use [Template tags and filters](template-tags.md) for rendering requirements and
[Admin mixin](admin-mixin.md) for column isolation and its opt-outs.
