"""An alphabet index for text fields in the admin changelist."""

from __future__ import annotations

from itertools import chain
from string import ascii_uppercase
from typing import TYPE_CHECKING, Any

from django.contrib.admin import SimpleListFilter
from django.contrib.admin.utils import get_fields_from_path, lookup_spawns_duplicates
from django.core.exceptions import ImproperlyConfigured
from django.db.models import TextField, Value
from django.db.models.functions import Coalesce, Substr
from django.db.models.lookups import In
from django.utils.translation import gettext

from .bidi import isolate
from .formatting import arabic_sort_expression, arabic_sort_key

if TYPE_CHECKING:
    from django.contrib.admin import ModelAdmin
    from django.db.models import Expression, Model, QuerySet
    from django.http import HttpRequest
    from django.utils.functional import _StrOrPromise


# Dictionary order rather than code point order (notably for پ, چ, ژ and گ).
_ARABIC = "ءابپتثجچحخدذرزژسشصضطظعغفقكکگلمنهويی"
_DIGITS = "0-9"
_OTHER = "other"


class ArabicInitialListFilter(SimpleListFilter):
    """Filter on the folded initial of ``field_name``, which may traverse relations."""

    field_name: str = ""
    include_latin = True
    include_digits = True

    def __init__(
        self,
        request: HttpRequest,
        params: dict[str, list[str]],
        model: type[Model],
        model_admin: ModelAdmin[Any],
    ) -> None:
        if not self.field_name:
            raise ImproperlyConfigured("ArabicInitialListFilter requires a field_name.")
        if self.title is None:
            self.title = get_fields_from_path(model, self.field_name)[-1].verbose_name
        if self.parameter_name is None:
            self.parameter_name = self.field_name.replace("__", "_") + "__initial"
        super().__init__(request, params, model, model_admin)

    def _initial(self) -> Substr:
        # Fold *before* slicing: a stored value can start with several ignored marks.
        key = Coalesce(arabic_sort_expression(self.field_name), Value(""), output_field=TextField())
        return Substr(key, 1, 1)

    def lookups(self, request: HttpRequest, model_admin: ModelAdmin[Any]) -> list[tuple[str, str]]:
        letters = _ARABIC + (ascii_uppercase if self.include_latin else "")
        buckets = {arabic_sort_key(letter): letter for letter in letters}
        # Seed each bucket with its folded initials, including letters absent
        # today (a bookmarked filter still works). Add any other characters
        # the database returned for that bucket: this avoids relying on SQL
        # regex digit classes or backend-specific non-ASCII lowercasing.
        self._members: dict[str, set[str]] = {letter: {key} for key, letter in buckets.items()}
        if self.include_digits:
            self._members[_DIGITS] = set("0123456789")
        present = set()
        qs = model_admin.get_queryset(request).order_by()  # No ordering columns in SELECT DISTINCT.
        for initial in qs.values_list(self._initial(), flat=True).distinct():
            key = arabic_sort_key(initial)[:1]
            bucket = (
                _DIGITS if self.include_digits and key.isdecimal() else buckets.get(key, _OTHER)
            )
            present.add(bucket)
            if bucket != _OTHER:
                self._members[bucket].add(initial)

        return [
            (bucket, isolate(gettext("Other") if bucket == _OTHER else bucket))
            for bucket in (*self._members, _OTHER)
            if bucket in present
        ]

    def queryset(self, request: HttpRequest, queryset: QuerySet[Any]) -> QuerySet[Any]:
        bucket = self.value()
        predicate: Expression
        if bucket == _OTHER:
            # Match the complement, not a potentially unbounded IN list of
            # punctuation, emoji, CJK characters, etc. NULL was folded to ''.
            predicate = ~In(self._initial(), list(chain.from_iterable(self._members.values())))
        elif bucket in self._members:
            predicate = In(self._initial(), self._members[bucket])
        else:
            return queryset
        result: QuerySet[Any] = queryset.filter(predicate)
        if lookup_spawns_duplicates(queryset.model._meta, self.field_name):
            result = result.distinct()
        return result


def arabic_initial_filter(
    field_name: str,
    *,
    title: _StrOrPromise | None = None,
    parameter_name: str | None = None,
    include_latin: bool = True,
    include_digits: bool = True,
) -> type[ArabicInitialListFilter]:
    """Return a filter class ready to put into a ``ModelAdmin.list_filter`` tuple."""

    class InitialFilter(ArabicInitialListFilter):
        pass

    InitialFilter.field_name = field_name
    InitialFilter.title = title
    InitialFilter.parameter_name = parameter_name
    InitialFilter.include_latin = include_latin
    InitialFilter.include_digits = include_digits
    return InitialFilter
