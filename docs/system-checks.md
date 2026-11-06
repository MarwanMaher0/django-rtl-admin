---
title: System checks | django-rtl-admin
description: Diagnose rtl_admin.W001 through W004 for app ordering, unknown configuration keys, the missing set_language endpoint, and LocaleMiddleware setup.
---

# System checks

The app registers three Django check functions that can emit four warning IDs.
Run them as part of your project's normal checks:

```sh
python manage.py check
```

All four are Django `Warning` objects, not validation errors. Their exact prefix
is `rtl_admin`, not `django_rtl_admin`. Registration occurs when
`django_rtl_admin.apps.RTLAdminConfig.ready()` imports the checks module.

| ID | Condition | Primary fix |
| --- | --- | --- |
| `rtl_admin.W001` | The RTL admin app is listed after contrib admin. | Put `django_rtl_admin` before `django.contrib.admin`. |
| `rtl_admin.W002` | `RTL_ADMIN` contains unsupported keys. | Correct or remove the reported keys. |
| `rtl_admin.W003` | The switcher is enabled and `set_language` cannot be reversed. | Route Django's language endpoint or disable the switcher. |
| `rtl_admin.W004` | The switcher is enabled and the exact `LocaleMiddleware` path is absent. | Add the middleware or disable the switcher. |

## `rtl_admin.W001`: app order

The check reads `INSTALLED_APPS`, stripping `.apps.…` from usual AppConfig paths.
If both `django_rtl_admin` and `django.contrib.admin` are present, the former must
appear first. If either is absent, this check is silent.

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
`admin/base_site.html`. Usual paths such as
`django_rtl_admin.apps.RTLAdminConfig` are recognized; arbitrary project-defined
AppConfig paths are not resolved through the app registry by this check.

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
key names only. Invalid `ISOLATION_DIRECTION`, `NUMERALS`, or
`LANGUAGE_SWITCHER_LABELS` choices raise `ImproperlyConfigured` when accessed;
they are not reported as W002. Other setting types are not comprehensively
validated, so use a dictionary and real booleans for switches.

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

## Disabling the switcher checks

If the switcher is not wanted, disable its feature rather than merely hiding
warnings:

```python
RTL_ADMIN = {
    "LANGUAGE_SWITCHER": False,
}
```

This skips both W003 and W004 and suppresses the form and its script. W001 and
W002 still run. W003 and W004 can occur together, and they still run with only
one configured language even though the form hides in that case.

## What a clean result does not guarantee

The checks do not validate `USE_I18N`, request/CSRF template context, custom
language-list validity, asset delivery, Babel availability, mixin attributes,
or effective template inheritance. They also do not verify middleware order.
Use [Template tags and filters](template-tags.md) for rendering requirements and
[Admin mixin](admin-mixin.md) for column isolation and its opt-outs.
