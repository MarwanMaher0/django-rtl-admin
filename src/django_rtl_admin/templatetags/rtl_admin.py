"""Template filters and tags: ``{% load rtl_admin %}``."""

from __future__ import annotations

import datetime
import logging
import unicodedata
from collections.abc import Sequence as SequenceABC
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
    from collections.abc import Iterable, Sequence

    from django.template.context import Context
    from django.utils.functional import Promise
    from django.utils.safestring import SafeString

register = template.Library()

logger = logging.getLogger("django_rtl_admin")


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
    if value is None or value == "":
        return ""
    try:
        places = None if decimal_pos is None or decimal_pos == "" else int(decimal_pos)
    except (TypeError, ValueError):
        places = None
    try:
        number = formatting._as_decimal(value)
        return formatting.format_number(number, decimal_pos=places)
    except (ArithmeticError, TypeError, ValueError):
        return str(value)


@register.filter(name="l10n_currency")
def l10n_currency(value: Any, currency: str | None = None) -> str:
    """Locale-aware money: ``{{ book.price|l10n_currency:"EGP" }}``."""
    try:
        return formatting.format_currency(value, currency)
    except (ArithmeticError, TypeError, ValueError):
        return str(value)


@register.filter(name="l10n_percent")
def l10n_percent(value: Any) -> str:
    """Locale-aware percentage from a 0..1 ratio."""
    if value is None or value == "":
        return ""
    try:
        number = formatting._as_decimal(value)
        return formatting.format_percent(number)
    except (ArithmeticError, TypeError, ValueError):
        return str(value)


@register.filter(name="l10n_date")
def l10n_date(value: datetime.date | None, fmt: str = "medium") -> str:
    """Locale-aware date: ``{{ book.published_on|l10n_date:"long" }}``."""
    if not isinstance(value, datetime.date):
        return ""
    try:
        return formatting.format_date(value, fmt)
    except (AttributeError, TypeError, ValueError):
        return ""


@register.filter(name="l10n_datetime", expects_localtime=True)
def l10n_datetime(value: datetime.datetime | None, fmt: str = "medium") -> str:
    """Locale-aware date and time."""
    if not isinstance(value, datetime.datetime):
        return ""
    try:
        return formatting._format_datetime(value, fmt)
    except (AttributeError, TypeError, ValueError):
        return ""


@register.filter(name="l10n_time", expects_localtime=True)
def l10n_time(
    value: datetime.time | datetime.datetime | None, fmt: str = "medium"
) -> str:
    """Locale-aware time of day."""
    if not isinstance(value, (datetime.time, datetime.datetime)):
        return ""
    try:
        return formatting._format_time(value, fmt)
    except (AttributeError, TypeError, ValueError):
        return ""


@register.filter(name="local_digits")
def local_digits(value: Any) -> Any:
    """Rewrite the digits in a ready-made string using the active locale's set."""
    if value is None:
        return ""
    try:
        return formatting.transliterate_digits(str(value), formatting.numbering_system())
    except (TypeError, ValueError):
        return value


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


#: Keywords that must stay unquoted in ``font-family``: the CSS generic
#: families, plus the two vendor system-font keywords that only work bare.
GENERIC_FONT_FAMILIES = frozenset(
    {
        "serif",
        "sans-serif",
        "monospace",
        "cursive",
        "fantasy",
        "system-ui",
        "ui-serif",
        "ui-sans-serif",
        "ui-monospace",
        "ui-rounded",
        "math",
        "emoji",
        "fangsong",
        "-apple-system",
        "blinkmacsystemfont",
    }
)

# A family name containing any of these could end the <style> element or the
# CSS rule it sits in, so the whole override is skipped.
_UNSAFE_FONT_CHARS = frozenset("<>{};")
_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")


class _FontStackError(ValueError):
    pass


def _read_css_string(value: str, index: int) -> tuple[str, int]:
    """Decode the CSS string starting at ``value[index]`` (a quote)."""
    quote = value[index]
    index += 1
    chars: list[str] = []
    while index < len(value):
        char = value[index]
        if char == quote:
            return "".join(chars), index + 1
        if char == "\\":
            index += 1
            if index >= len(value):
                break
            end = index
            while end < len(value) and end - index < 6 and value[end] in _HEX_DIGITS:
                end += 1
            if end > index:
                codepoint = int(value[index:end], 16)
                if codepoint == 0 or 0xD800 <= codepoint <= 0xDFFF or codepoint > 0x10FFFF:
                    codepoint = 0xFFFD
                chars.append(chr(codepoint))
                if end < len(value) and value[end] in " \t\n":
                    end += 1
                index = end
                continue
        chars.append(value[index])
        index += 1
    raise _FontStackError("unterminated quoted family name")


def _parse_font_families(value: str) -> list[tuple[str, bool]]:
    """Split a CSS ``font-family`` list into ``(name, was_quoted)`` pairs."""
    families: list[tuple[str, bool]] = []
    index = 0
    while index < len(value):
        if value[index].isspace() or value[index] == ",":
            index += 1
            continue
        if value[index] in "\"'":
            name, index = _read_css_string(value, index)
            while index < len(value) and value[index].isspace():
                index += 1
            if index < len(value) and value[index] != ",":
                raise _FontStackError("unexpected text after a quoted family name")
            families.append((name, True))
            continue
        end = value.find(",", index)
        if end == -1:
            end = len(value)
        raw = value[index:end]
        if any(char in raw for char in "\"'\\"):
            raise _FontStackError("stray quote or backslash in an unquoted family name")
        families.append((" ".join(raw.split()), False))
        index = end
    return families


def _sequence_font_family(item: str) -> tuple[str, bool]:
    """One sequence entry: a pre-quoted CSS string, a keyword, or a raw name."""
    item = item.strip()
    if item[:1] in ("\"", "'"):
        try:
            name, end = _read_css_string(item, 0)
        except _FontStackError:
            pass
        else:
            if end == len(item):
                return name, True
    return " ".join(item.split()), False


def _css_font_family(name: str, quoted: bool) -> str:
    if any(
        char in _UNSAFE_FONT_CHARS or unicodedata.category(char) == "Cc"
        for char in name
    ):
        raise _FontStackError(f"unsafe character in family name {name!r}")
    if not quoted and name.lower() in GENERIC_FONT_FAMILIES:
        return name
    return '"' + name.replace("\\", "\\\\").replace('"', '\\"') + '"'


def css_font_stack(value: Any) -> str:
    """Serialize ``FONT_STACK`` as a CSS ``font-family`` list.

    A string is read as a CSS family list (``'"Noto Naskh Arabic", serif'``);
    each entry of a sequence is one family name, raw or already quoted.
    Family names come out as CSS strings with ``\\`` and ``"`` escaped,
    generic keywords (``serif``, ``system-ui``...) stay bare, and pre-quoted
    names are decoded and re-quoted.  Returns ``""`` -- and logs a warning --
    when the value is malformed or contains a character that could close the
    ``<style>`` element or the CSS rule.
    """
    if not value:
        return ""
    try:
        if isinstance(value, str):
            names = _parse_font_families(value)
        elif isinstance(value, SequenceABC) and all(isinstance(item, str) for item in value):
            names = [_sequence_font_family(item) for item in value]
        else:
            raise _FontStackError("expected a string or a sequence of strings")
        families = [_css_font_family(name, quoted) for name, quoted in names if name]
    except _FontStackError as exc:
        logger.warning(
            "Ignoring RTL_ADMIN['FONT_STACK'] = %r: %s. The shipped font stack is used instead.",
            value,
            exc,
        )
        return ""
    return ", ".join(families)


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
    font_stack = css_font_stack(rtl_settings.FONT_STACK)
    if font_stack:
        # <style> is raw text: entities are not decoded there, so the stack is
        # inserted verbatim.  css_font_stack() has rejected "<", ">", "{", "}"
        # and ";", and every family name is a quoted CSS string or a keyword.
        html += format_html(
            "<style{}>:root {{ --rtl-admin-font-stack: {}; }}</style>",
            nonce,
            mark_safe(font_stack),
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
