"""Template filters and tags: ``{% load rtl_admin %}``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict

import django
from django import template
from django.conf import settings
from django.templatetags.static import static
from django.urls import NoReverseMatch, reverse
from django.utils.html import conditional_escape, format_html, format_html_join
from django.utils.safestring import mark_safe
from django.utils.translation import get_language, get_language_info
from django.utils.translation import gettext as _

from .. import bidi as bidi_module
from .. import formatting
from ..conf import rtl_settings

if TYPE_CHECKING:
    import datetime
    from collections.abc import Iterable, Sequence

    from django.template.context import Context
    from django.utils.functional import Promise
    from django.utils.safestring import SafeString

register = template.Library()


# ---------------------------------------------------------------------------
# Bidirectional text
# ---------------------------------------------------------------------------


@register.filter(name="bidi_isolate", is_safe=True, needs_autoescape=True)
def bidi_isolate(
    value: Any, direction: str | None = None, autoescape: bool = True
) -> SafeString:
    """Wrap the whole value in a Unicode isolate.

    ``{{ book.isbn|bidi_isolate }}`` renders ``978-0-13-468599-1`` the right
    way round even in the middle of an Arabic sentence.  Pass ``"ltr"`` or
    ``"rtl"`` to force the direction: ``{{ value|bidi_isolate:"ltr" }}``.
    """
    return bidi_module.mark_isolated(value, direction, autoescape=autoescape)


@register.filter(name="bidi_runs", is_safe=True, needs_autoescape=True)
def bidi_runs(value: Any, base: str | None = None, autoescape: bool = True) -> SafeString:
    """Isolate only the embedded opposite-direction runs inside the value.

    Use it on prose that mixes scripts, where wrapping the whole string would
    be too blunt: ``{{ note|bidi_runs }}``.
    """
    return bidi_module.mark_isolated_runs(value, base, autoescape=autoescape)


@register.filter(name="bidi_strip", is_safe=True)
def bidi_strip(value: Any) -> str:
    """Remove every isolate and directional mark from the value."""
    return bidi_module.strip_isolates("" if value is None else str(value))


@register.filter(name="bidi_dir")
def bidi_dir(value: Any, default: str = "ltr") -> str:
    """First-strong direction of the value: ``"rtl"`` or ``"ltr"``.

    Handy for ``dir`` attributes: ``<td dir="{{ value|bidi_dir }}">``.
    """
    return bidi_module.text_direction("" if value is None else str(value), default)


# ---------------------------------------------------------------------------
# Locale-aware formatting
# ---------------------------------------------------------------------------


@register.filter(name="l10n_number")
def l10n_number(value: Any, decimal_pos: int | str | None = None) -> str:
    """Locale-aware number, in the locale's own numbering system."""
    places = None if decimal_pos is None or decimal_pos == "" else int(decimal_pos)
    return formatting.format_number(value, decimal_pos=places)


@register.filter(name="l10n_currency")
def l10n_currency(value: Any, currency: str | None = None) -> str:
    """Locale-aware money: ``{{ book.price|l10n_currency:"EGP" }}``."""
    return formatting.format_currency(value, currency)


@register.filter(name="l10n_percent")
def l10n_percent(value: Any) -> str:
    """Locale-aware percentage from a 0..1 ratio."""
    return formatting.format_percent(value)


@register.filter(name="l10n_date")
def l10n_date(value: datetime.date | None, fmt: str = "medium") -> str:
    """Locale-aware date: ``{{ book.published_on|l10n_date:"long" }}``."""
    return formatting.format_date(value, fmt)


@register.filter(name="l10n_datetime", expects_localtime=True)
def l10n_datetime(value: datetime.datetime | None, fmt: str = "medium") -> str:
    """Locale-aware date and time."""
    return formatting._format_datetime(value, fmt)


@register.filter(name="l10n_time", expects_localtime=True)
def l10n_time(
    value: datetime.time | datetime.datetime | None, fmt: str = "medium"
) -> str:
    """Locale-aware time of day."""
    return formatting._format_time(value, fmt)


@register.filter(name="local_digits")
def local_digits(value: Any) -> str:
    """Rewrite the digits in a ready-made string using the active locale's set."""
    if value is None:
        return ""
    return formatting.transliterate_digits(str(value), formatting.numbering_system())


# ---------------------------------------------------------------------------
# Direction helpers
# ---------------------------------------------------------------------------


@register.simple_tag(name="rtl_admin_direction")
def rtl_admin_direction() -> str:
    """``"rtl"`` or ``"ltr"`` for the active language."""
    return bidi_module.current_direction()


@register.simple_tag(name="rtl_admin_body_class")
def rtl_admin_body_class() -> str:
    """Body classes that switch the stylesheet's behaviour on and off."""
    classes = ["rtl-admin", f"rtl-admin--{bidi_module.current_direction()}"]
    if rtl_settings.ISOLATE_TABLE_CELLS:
        classes.append("rtl-admin--isolate-cells")
    if rtl_settings.PLAINTEXT_FORM_FIELDS:
        classes.append("rtl-admin--plaintext-fields")
    return " ".join(classes)


@register.simple_tag(name="rtl_admin_site_name_tag")
def rtl_admin_site_name_tag() -> str:
    """``h1`` or ``div`` -- whichever the running Django's admin CSS expects."""
    return "h1" if django.VERSION < (5, 0) else "div"


def _nonce_attr(context: Context | None) -> str:
    """``nonce="..."`` when the project is using Django's CSP support.

    Django 6.0 puts a ``csp_nonce`` in the template context when the CSP
    context processor is enabled.  Reading the key rather than checking a
    version keeps this a no-op on every other Django.
    """
    nonce = context.get("csp_nonce") if context else None
    if nonce is None:
        return ""
    return format_html(' nonce="{}"', nonce)


@register.filter(name="rtl_admin_accessible_viewport", is_safe=True)
def rtl_admin_accessible_viewport(value: Any) -> str:
    return str(value).replace(
        'content="user-scalable=no, width=device-width, initial-scale=1.0, maximum-scale=1.0"',
        'content="width=device-width, initial-scale=1.0"',
    )


@register.filter(name="rtl_admin_result_object")
def rtl_admin_result_object(results: Sequence[Any], index: int) -> Any:
    return results[index]


@register.filter(name="rtl_admin_action_label")
def rtl_admin_action_label(value: str, obj: Any) -> str:
    html = str(conditional_escape(value))
    if 'class="action-select"' not in html or "aria-label=" in html:
        return value
    label = format_html(_("Select this object for an action - {}"), obj)
    attributes = format_html('class="action-select" aria-label="{}"', label)
    return mark_safe(html.replace('class="action-select"', str(attributes), 1))


@register.simple_tag(takes_context=True, name="rtl_admin_styles")
def rtl_admin_styles(context: Context | None = None) -> str:
    """The ``<link>`` (and optional font override) for the admin stylesheet."""
    if not rtl_settings.ENABLE_CSS:
        return ""
    nonce = _nonce_attr(context)
    html = format_html(
        '<link rel="stylesheet" href="{}"{}>',
        static("django_rtl_admin/css/rtl-admin.css"),
        nonce,
    )
    font_stack = rtl_settings.FONT_STACK
    if font_stack:
        if not isinstance(font_stack, str):
            font_stack = ", ".join(font_stack)
        html += format_html(
            "<style{}>:root {{ --rtl-admin-font-stack: {}; }}</style>",
            nonce,
            font_stack,
        )
    return html


@register.simple_tag(takes_context=True, name="rtl_admin_scripts")
def rtl_admin_scripts(context: Context | None = None) -> str:
    """Progressive-enhancement script for the language switcher."""
    if not rtl_settings.LANGUAGE_SWITCHER:
        return ""
    return format_html(
        '<script src="{}" defer{}></script>',
        static("django_rtl_admin/js/language_switcher.js"),
        _nonce_attr(context),
    )


# ---------------------------------------------------------------------------
# Language switcher
# ---------------------------------------------------------------------------


class SwitcherLanguage(TypedDict):
    """One language offered by the switcher."""

    code: str
    label: str | Promise
    bidi: bool
    is_active: bool


def _label_for(code: str, configured_label: str | Promise | None) -> str | Promise:
    try:
        info = get_language_info(code)
    except KeyError:
        return configured_label or code
    style = rtl_settings.LANGUAGE_SWITCHER_LABELS
    native = info.get("name_local") or info.get("name") or code
    translated = configured_label or info.get("name") or code
    if style == "native":
        return native
    if style == "translated":
        return translated
    if str(native) == str(translated):
        return native
    # Isolate the parenthesised half: without it the brackets around a Latin
    # name break out of an Arabic option label and end up on the wrong side.
    return f"{native} {bidi_module.isolate(f'({translated})')}"


def switcher_languages() -> list[SwitcherLanguage]:
    """The ``(code, label, bidi, is_active)`` rows shown by the switcher."""
    configured = rtl_settings.LANGUAGE_SWITCHER_LANGUAGES
    if configured is None:
        configured = getattr(settings, "LANGUAGES", ())
    rows: list[SwitcherLanguage] = []
    active = (get_language() or "").lower()
    label: str | Promise | None
    for entry in configured:
        if isinstance(entry, str):
            code, label = entry, None
        else:
            code, label = entry[0], entry[1]
        rows.append(
            {
                "code": code,
                "label": _label_for(code, label),
                "bidi": bidi_module.is_rtl_language(code),
                "is_active": code.lower() == active,
            }
        )
    return rows


@register.inclusion_tag(
    "django_rtl_admin/language_switcher.html",
    takes_context=True,
    name="rtl_admin_language_switcher",
)
def rtl_admin_language_switcher(context: Context) -> dict[str, Any]:
    """Render the admin language switcher.

    Silently renders nothing when the switcher is turned off, when fewer than
    two languages are configured, or when ``django.conf.urls.i18n`` is not
    routed (there is nowhere to POST to).
    """
    if not rtl_settings.LANGUAGE_SWITCHER:
        return {"enabled": False}
    languages = switcher_languages()
    if len(languages) < 2:
        return {"enabled": False}
    try:
        set_language_url = reverse("set_language")
    except NoReverseMatch:
        return {"enabled": False}
    request = context.get("request")
    return {
        "enabled": True,
        "languages": languages,
        "set_language_url": set_language_url,
        "redirect_to": request.get_full_path() if request is not None else "",
        "csrf_token": context.get("csrf_token", ""),
    }


@register.simple_tag(name="rtl_admin_language_links")
def rtl_admin_language_links() -> list[SwitcherLanguage]:
    """The switcher's languages as plain data, for custom templates."""
    return switcher_languages()


@register.simple_tag(name="rtl_admin_isolated_join")
def rtl_admin_isolated_join(values: Iterable[Any] | None, separator: str = ", ") -> str:
    """Join values, isolating each one -- for list columns in a mixed admin."""
    values = list(values or [])
    if not values:
        return ""
    return mark_safe(
        format_html_join(
            separator, "{}", ((bidi_module.mark_isolated(v),) for v in values)
        )
    )
