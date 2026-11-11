"""Unicode bidirectional-text helpers.

The Unicode Bidirectional Algorithm reorders text at display time.  That is
exactly what you want for prose, and exactly what you do not want for opaque
identifiers.  Inside an Arabic sentence, the innocent string ``v1.2.3`` or
``978-0-13-468599-1`` or ``2024-03-05`` is reordered by the browser and the
user reads it backwards -- the characters are intact in the database, but the
human sees a different value.

The fix is to wrap such runs in Unicode *isolates* (U+2066 LRI, U+2067 RLI,
U+2068 FSI, terminated by U+2069 PDI).  An isolate tells the algorithm to
resolve the enclosed run on its own and treat the whole thing as a single
neutral object in the surrounding paragraph.

Isolates are plain characters, not markup, so they survive escaping, copy and
paste, ``json.dumps`` and database round-trips.
"""

from __future__ import annotations

import unicodedata
from typing import Any

from django.conf import settings
from django.utils.html import conditional_escape, escape
from django.utils.safestring import SafeString, mark_safe
from django.utils.translation import get_language

from .conf import rtl_settings

#: Left-to-right isolate.
LRI = "⁦"
#: Right-to-left isolate.
RLI = "⁧"
#: First-strong isolate: direction is taken from the first strong character.
FSI = "⁨"
#: Pop directional isolate: terminates LRI, RLI or FSI.
PDI = "⁩"

#: Legacy marks, kept because some consumers (plain-text exports, terminals)
#: still handle these better than isolates.
LRM = "‎"
RLM = "‏"

ISOLATE_OPENERS = frozenset({LRI, RLI, FSI})
#: Every character this module ever inserts.
ISOLATE_CHARS = frozenset({LRI, RLI, FSI, PDI, LRM, RLM})

_OPENER_FOR = {"ltr": LRI, "rtl": RLI, "auto": FSI}

# Character classes used by :func:`isolate_runs`.
_STRONG_RTL = frozenset({"R", "AL"})
_NUMERIC = frozenset({"EN", "AN"})


def _char_class(char: str) -> str:
    """Return ``"L"``, ``"R"``, ``"N"`` (number) or ``"O"`` (neutral)."""
    bidi = unicodedata.bidirectional(char)
    if bidi == "L":
        return "L"
    if bidi in _STRONG_RTL:
        return "R"
    if bidi in _NUMERIC:
        return "N"
    return "O"


def rtl_languages() -> frozenset[str]:
    """Every language code this package treats as right-to-left.

    Combines the entries of ``settings.LANGUAGES_BIDI`` that Django can
    actually match with ``RTL_ADMIN["EXTRA_RTL_LANGUAGES"]``, normalized the
    same way :func:`is_rtl_language` matches them.  Raw regional or upper-case
    ``LANGUAGES_BIDI`` entries are omitted: Django compares the base subtag to
    the raw entries, so those never make a language RTL.  The per-language
    ``bidi`` flag in Django's ``LANG_INFO`` is deliberately not consulted: it
    can disagree with ``LANGUAGES_BIDI``, and the document direction follows
    the latter.
    """
    codes = {
        code
        for code in settings.LANGUAGES_BIDI
        if isinstance(code, str)
        and code == code.lower()
        and "-" not in code
        and "_" not in code
    }
    codes.update(
        extra.replace("_", "-").lower()
        for extra in rtl_settings.EXTRA_RTL_LANGUAGES
    )
    return frozenset(codes)


def is_rtl_language(language_code: str | None = None) -> bool:
    """Is ``language_code`` (default: the active language) right-to-left?

    ``LANGUAGES_BIDI`` is matched exactly as Django's ``get_language_bidi()``
    does -- the code's base subtag against the raw entries, case-sensitively --
    so the body class always agrees with the document's ``dir`` attribute.
    ``EXTRA_RTL_LANGUAGES`` stays additive and is matched case-insensitively.
    """
    code = (language_code or get_language() or "").replace("_", "-").lower()
    # "ar-eg" -> "ar", like Django's get_language_bidi().
    base = code.split("-", 1)[0]
    if base in settings.LANGUAGES_BIDI:
        return True
    extras = {
        extra.replace("_", "-").lower()
        for extra in rtl_settings.EXTRA_RTL_LANGUAGES
    }
    return code in extras or base in extras


def current_direction() -> str:
    """``"rtl"`` or ``"ltr"`` for the currently active language."""
    return "rtl" if is_rtl_language() else "ltr"


def text_direction(value: str, default: str = "ltr") -> str:
    """First-strong direction of ``value`` -- what ``dir="auto"`` would pick."""
    for char in value or "":
        cls = _char_class(char)
        if cls == "L":
            return "ltr"
        if cls == "R":
            return "rtl"
    return default


def has_mixed_direction(value: str) -> bool:
    """True when ``value`` contains both strong LTR and strong RTL characters."""
    seen = {_char_class(c) for c in value or ""}
    return "L" in seen and "R" in seen


def _resolve_direction(direction: str | None) -> str:
    if direction in (None, "", "default"):
        direction = rtl_settings.ISOLATION_DIRECTION
    if direction not in _OPENER_FOR:
        raise ValueError(
            f"direction must be one of 'auto', 'ltr', 'rtl'; got {direction!r}"
        )
    return direction


def isolate(value: str, direction: str | None = None) -> str:
    """Wrap ``value`` in a Unicode isolate.  Plain text in, plain text out.

    ``direction`` is ``"auto"`` (U+2068 FSI), ``"ltr"`` (U+2066 LRI) or
    ``"rtl"`` (U+2067 RLI); the default comes from
    ``RTL_ADMIN["ISOLATION_DIRECTION"]``.
    """
    if value is None:
        return ""
    text = value if isinstance(value, str) else str(value)
    if not text:
        return text
    return _OPENER_FOR[_resolve_direction(direction)] + text + PDI


def strip_isolates(value: str) -> str:
    """Remove every isolate/mark character this module may have inserted."""
    if not value:
        return value
    return "".join(c for c in value if c not in ISOLATE_CHARS)


def is_isolated(value: str) -> bool:
    """True when ``value`` is already wrapped in a single isolate."""
    return bool(value) and value[0] in ISOLATE_OPENERS and value[-1] == PDI


def mark_isolated(
    value: Any, direction: str | None = None, autoescape: bool = True
) -> SafeString:
    """Escape ``value`` if needed, wrap it in an isolate, return a ``SafeString``.

    This is the helper to reach for in ``ModelAdmin`` display methods and
    anywhere else HTML is produced::

        @admin.display(description="Reference")
        def reference(self, obj):
            return mark_isolated(obj.reference)

    The value is escaped *before* the isolate characters are added, so HTML in
    the value stays inert.  Values that are already marked safe (or expose
    ``__html__``) are passed through unescaped, exactly like Django's own
    ``conditional_escape``.
    """
    if value is None:
        return mark_safe("")
    escaped = conditional_escape(value) if autoescape else _as_text(value)
    if not escaped:
        return mark_safe("")
    return mark_safe(isolate(escaped, direction))


def _as_text(value: Any) -> str:
    if isinstance(value, SafeString):
        return value
    if hasattr(value, "__html__"):
        html: str = value.__html__()
        return html
    return str(value)


def isolate_runs(value: str, base: str | None = None) -> str:
    """Isolate each *embedded* opposite-direction run inside ``value``.

    Unlike :func:`isolate`, which treats the whole string as one unit, this
    walks the string and wraps only the parts that the bidi algorithm would
    reorder: Latin words inside Arabic prose, and -- in an RTL paragraph --
    punctuated numeric runs such as ``2024-03-05``, ``1.2.3`` or ``10:45:02``.

    Plain text in, plain text out.  ``base`` defaults to the direction of the
    active language.
    """
    if not value:
        return value
    if base is None:
        base = current_direction()
    if base not in ("ltr", "rtl"):
        raise ValueError(f"base must be 'ltr' or 'rtl'; got {base!r}")

    opener = LRI if base == "rtl" else RLI
    base_strong = "R" if base == "rtl" else "L"
    classes = [_char_class(char) for char in value]

    out: list[str] = []
    index = 0
    length = len(value)
    while index < length:
        if classes[index] == base_strong:
            out.append(value[index])
            index += 1
            continue
        segment_start = index
        while index < length and classes[index] != base_strong:
            index += 1
        segment_end = index
        start, end = _trim_edges(value, classes, segment_start, segment_end)
        out.append(value[segment_start:start])
        run = value[start:end]
        if run and _needs_isolation(classes[start:end], base):
            out.append(opener + run + PDI)
        else:
            out.append(run)
        out.append(value[end:segment_end])
    return "".join(out)


def mark_isolated_runs(
    value: Any, base: str | None = None, autoescape: bool = True
) -> SafeString:
    """HTML-safe :func:`isolate_runs`.

    Isolation happens on the *raw* text and escaping afterwards, so an isolate
    character can never land in the middle of an HTML entity.

    Values that are already marked safe are returned untouched: inserting
    isolates into existing markup could land inside a tag or an attribute.
    Call :func:`isolate_runs` yourself on the text before you build the HTML.
    """
    if value is None:
        return mark_safe("")
    if isinstance(value, SafeString) or hasattr(value, "__html__"):
        return mark_safe(_as_text(value))
    text = str(value)
    if not text:
        return mark_safe("")
    isolated = isolate_runs(text, base)
    return mark_safe(escape(isolated) if autoescape else isolated)


def _trim_edges(value: str, classes: list[str], start: int, end: int) -> tuple[int, int]:
    """Decide how much of a run's neutral fringe belongs to the run.

    Punctuation glued to the run travels with it -- the leading slash of
    ``/srv/archive/report.pdf`` is precisely the character that jumps to the
    wrong end otherwise.  Punctuation separated from it by a space belongs to
    the surrounding sentence and stays outside.
    """
    prefix_end = start
    while prefix_end < end and classes[prefix_end] == "O":
        prefix_end += 1
    for index in range(prefix_end - 1, start - 1, -1):
        if value[index].isspace():
            start = index + 1
            break

    suffix_start = end
    while suffix_start > start and classes[suffix_start - 1] == "O":
        suffix_start -= 1
    for index in range(suffix_start, end):
        if value[index].isspace():
            end = index
            break

    return start, end


def _needs_isolation(run_classes: list[str], base: str) -> bool:
    """Would this run be visually reordered by the bidi algorithm?"""
    opposite = "L" if base == "rtl" else "R"
    if opposite in run_classes:
        return True
    if base == "rtl":
        # A bare number is fine; a punctuated one ("2024-03-05", "1.2.3",
        # "10:45") is the classic reordering victim.
        return "N" in run_classes and "O" in run_classes
    return False
