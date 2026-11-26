"""CSV export actions: options, Arabic text, spreadsheet safety, streaming."""

import csv
import io
from datetime import date, datetime, time
from datetime import timezone as dt_timezone
from decimal import Decimal
from urllib.parse import quote

import pytest
from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import AnonymousUser, Permission
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.db.models import QuerySet
from django.test import RequestFactory, override_settings
from django.utils import timezone, translation
from django.utils.html import format_html
from django.utils.translation import gettext_lazy

from django_rtl_admin import export_as_csv, make_csv_export_action
from django_rtl_admin.bidi import BIDI_CONTROL_CHARS

from .testapp.models import Book, Category, Thing

pytestmark = pytest.mark.django_db

URL = "/admin/testapp/thing/"
BOM = b"\xef\xbb\xbf"


def plain_admin(model=Thing, **attrs):
    cls = type("ExportAdmin", (admin.ModelAdmin,), attrs)
    return cls(model, AdminSite())


def run(action, modeladmin, user, queryset=None):
    request = RequestFactory().post(URL)
    request.user = user
    if queryset is None:
        queryset = modeladmin.model.objects.all()
    return action(modeladmin, request, queryset)


def raw_bytes(response):
    return b"".join(response.streaming_content)


def table(response):
    return list(csv.reader(io.StringIO(raw_bytes(response).decode("utf-8-sig"))))


def shout(obj):
    return obj.name.upper()


shout.short_description = "صوت عالٍ"


# -- defaults ----------------------------------------------------------------


def test_default_export_follows_list_display(admin_user, thing, thing_admin):
    response = run(export_as_csv, thing_admin, admin_user)
    assert response.streaming
    assert response["Content-Type"] == "text/csv; charset=utf-8"
    data = raw_bytes(response)
    assert data.startswith(BOM)
    text = data.decode("utf-8-sig")
    # BidiSafeAdminMixin wraps changelist cells in isolates; none survive.
    assert not any(char in text for char in BIDI_CONTROL_CHARS)
    assert list(csv.reader(io.StringIO(text))) == [
        ["name", "name ar", "reference", "quantity", "is active", "Upper"],
        ["Deep Learning", "التعلم العميق", "978-0-262-03561-3", "1234", "True", "DEEP LEARNING"],
    ]


def test_export_works_on_a_plain_modeladmin(admin_user, thing):
    modeladmin = plain_admin(list_display=("name", "quantity"))
    assert table(run(export_as_csv, modeladmin, admin_user)) == [
        ["name", "quantity"],
        ["Deep Learning", "1234"],
    ]


def test_only_the_selected_rows_are_exported(admin_user, thing):
    other = Thing.objects.create(name="كتاب آخر", quantity=7)
    modeladmin = plain_admin(list_display=("name",))
    response = run(export_as_csv, modeladmin, admin_user, Thing.objects.filter(pk=other.pk))
    assert table(response) == [["name"], ["كتاب آخر"]]


def test_empty_queryset_exports_only_the_header(admin_user, db):
    modeladmin = plain_admin(list_display=("name", "quantity"))
    assert table(run(export_as_csv, modeladmin, admin_user)) == [["name", "quantity"]]


def test_action_metadata():
    assert export_as_csv.__name__ == "export_as_csv"
    assert export_as_csv.allowed_permissions == ["view"]
    with translation.override("en"):
        assert str(export_as_csv.short_description) == "Export selected rows as CSV"
    action = make_csv_export_action()
    assert action.__name__.startswith("export_csv_")
    assert action.allowed_permissions == ["view"]
    with translation.override("en"):
        assert str(action.short_description) == "Export selected rows as CSV"


def test_label_is_translated_in_the_active_language():
    with translation.override("ar"):
        assert str(export_as_csv.short_description) == "تصدير الصفوف المحددة بصيغة CSV"
    with translation.override("en"):
        assert str(export_as_csv.short_description) == "Export selected rows as CSV"


def test_factory_actions_get_distinct_names_and_coexist(admin_user, thing):
    first = make_csv_export_action(fields=("name",))
    second = make_csv_export_action(fields=("quantity",), delimiter=";")
    assert first.__name__ != second.__name__
    assert first.__name__.startswith("export_csv_")
    assert second.__name__.startswith("export_csv_")
    # Same options give the same stable name; different options differ.
    assert make_csv_export_action(fields=("name",)).__name__ == first.__name__

    class MultiAdmin(admin.ModelAdmin):
        actions = (export_as_csv, first, second)

    modeladmin = MultiAdmin(Thing, AdminSite())
    request = RequestFactory().get(URL)
    request.user = admin_user
    actions = modeladmin.get_actions(request)
    assert "export_as_csv" in actions
    assert first.__name__ in actions
    assert second.__name__ in actions
    # Each registered action still exports its own columns.
    assert table(run(first, modeladmin, admin_user))[0] == ["name"]
    assert table(run(second, modeladmin, admin_user))[0] == ["quantity"]


def test_action_hidden_without_view_permission(thing, django_user_model):
    user = django_user_model.objects.create_user(username="noview", password="pw", is_staff=True)

    class MultiAdmin(admin.ModelAdmin):
        actions = (export_as_csv, make_csv_export_action(fields=("name",)))

    modeladmin = MultiAdmin(Thing, AdminSite())
    request = RequestFactory().get(URL)
    request.user = user
    actions = modeladmin.get_actions(request)
    assert "export_as_csv" not in actions
    assert not any(name.startswith("export_csv_") for name in actions)


# -- columns and headers -------------------------------------------------------


def test_fields_option_sets_columns_and_order(admin_user, thing):
    action = make_csv_export_action(fields=("name_ar", shout, "slug"))
    assert table(run(action, plain_admin(), admin_user)) == [
        ["name ar", "صوت عالٍ", "Slug"],
        ["التعلم العميق", "DEEP LEARNING", "deep-learning"],
    ]


def test_admin_methods_and_model_properties(admin_user, thing):
    class MethodAdmin(admin.ModelAdmin):
        list_display = ("slug", "shout")

        @admin.display(description="الشكل الكبير")
        def shout(self, obj):
            return obj.name.upper()

    modeladmin = MethodAdmin(Thing, AdminSite())
    assert table(run(export_as_csv, modeladmin, admin_user)) == [
        ["Slug", "الشكل الكبير"],
        ["deep-learning", "DEEP LEARNING"],
    ]


def test_header_name_option_uses_raw_names(admin_user, thing, thing_admin):
    action = make_csv_export_action(header="name")
    header = table(run(action, thing_admin, admin_user))[0]
    assert header == ["name", "name_ar", "reference", "quantity", "is_active", "upper_name"]
    action = make_csv_export_action(fields=(shout,), header="name")
    assert table(run(action, plain_admin(), admin_user))[0] == ["shout"]


def test_headers_are_translated_in_the_request_language(admin_user, thing):
    class TranslatedAdmin(admin.ModelAdmin):
        list_display = ("search_column",)

        @admin.display(description=gettext_lazy("Search"))
        def search_column(self, obj):
            return obj.name

    modeladmin = TranslatedAdmin(Thing, AdminSite())
    with translation.override("ar"):
        response = run(export_as_csv, modeladmin, admin_user)
    # Consumed outside the override: the generator kept the request language.
    assert table(response)[0] == ["ابحث"]
    with translation.override("en"):
        response = run(export_as_csv, modeladmin, admin_user)
    assert table(response)[0] == ["Search"]


def test_arabic_verbose_name_header(admin_user, thing, monkeypatch):
    monkeypatch.setattr(Thing._meta.get_field("name"), "verbose_name", "الاسم الكامل")
    modeladmin = plain_admin(list_display=("name",))
    assert table(run(export_as_csv, modeladmin, admin_user)) == [
        ["الاسم الكامل"],
        ["Deep Learning"],
    ]


# -- filenames -----------------------------------------------------------------


def test_default_filename_uses_the_translated_plural(admin_user, thing, monkeypatch):
    monkeypatch.setattr(Thing._meta, "verbose_name_plural", "الأشياء")
    response = run(export_as_csv, plain_admin(), admin_user)
    disposition = response["Content-Disposition"]
    assert "filename*=UTF-8''" + quote("الأشياء.csv", safe="") in disposition
    assert 'filename="alashyaa.csv"' in disposition


def test_ascii_default_filename(admin_user, thing):
    response = run(export_as_csv, plain_admin(), admin_user)
    assert response["Content-Disposition"] == (
        "attachment; filename=\"things.csv\"; filename*=UTF-8''things.csv"
    )


def test_custom_filename_option(admin_user, thing):
    action = make_csv_export_action(filename="تقرير الكتب.csv")
    disposition = run(action, plain_admin(), admin_user)["Content-Disposition"]
    assert "filename*=UTF-8''" + quote("تقرير الكتب.csv", safe="") in disposition
    assert 'filename="tqryr-alktb.csv"' in disposition
    action = make_csv_export_action(filename="report.csv")
    assert run(action, plain_admin(), admin_user)["Content-Disposition"] == (
        "attachment; filename=\"report.csv\"; filename*=UTF-8''report.csv"
    )


# -- digits ---------------------------------------------------------------------


def test_digits_default_converts_arabic_and_persian_to_latin(admin_user):
    Thing.objects.create(name="الإصدار ١٢٣", reference="رقم ۴۵۶")
    action = make_csv_export_action(fields=("name", "reference"))
    assert table(run(action, plain_admin(), admin_user))[1] == ["الإصدار 123", "رقم 456"]


def test_digits_native_uses_the_active_numbering_system(admin_user, thing):
    action = make_csv_export_action(fields=("quantity",), digits="native")
    with translation.override("ar-eg"):
        response = run(action, plain_admin(), admin_user)
    assert table(response)[1] == ["١٢٣٤"]
    with translation.override("fa"):
        response = run(action, plain_admin(), admin_user)
    assert table(response)[1] == ["۱۲۳۴"]
    with translation.override("en"):
        response = run(action, plain_admin(), admin_user)
    assert table(response)[1] == ["1234"]


def test_digits_native_round_trips_stored_arabic_digits(admin_user):
    Thing.objects.create(name="الإصدار ١٢٣", quantity=45)
    action = make_csv_export_action(fields=("name", "quantity"), digits="native")
    with translation.override("ar-eg"):
        response = run(action, plain_admin(), admin_user)
    assert table(response)[1] == ["الإصدار ١٢٣", "٤٥"]


def test_digits_native_keeps_iso_dates_and_datetimes_ascii(admin_user):
    Book.objects.create(
        title="الطبعة 12",
        isbn="978-9953-0-0001-1",
        published_on=date(2024, 3, 5),
        available_from=datetime(2025, 1, 1, 9, 30, tzinfo=dt_timezone.utc),
        launch_time=time(18, 45),
    )
    action = make_csv_export_action(
        fields=("title", "published_on", "available_from", "launch_time"), digits="native"
    )
    with translation.override("ar-eg"), timezone.override("UTC"):
        response = run(action, plain_admin(Book), admin_user)
    row = table(response)[1]
    # Non-date text still gets native digits...
    assert row[0] == "الطبعة ١٢"
    # ...but ISO 8601 date, datetime and time cells keep ASCII digits.
    assert row[1] == "2024-03-05"
    assert row[2] == "2025-01-01T09:30:00+00:00"
    assert row[3] == "18:45:00"


# -- spreadsheet safety -----------------------------------------------------------


def test_formula_injection_is_neutralised(admin_user):
    Thing.objects.create(name="=SUM(A1:A2)", reference="+cmd", note="-3", price=Decimal("-5.00"))
    Thing.objects.create(name="\tcmd", note="\r@cmd")
    action = make_csv_export_action(fields=("name", "reference", "note", "price"))
    rows = table(run(action, plain_admin(), admin_user, Thing.objects.order_by("pk")))[1:]
    assert rows[0] == ["'=SUM(A1:A2)", "'+cmd", "'-3", "'-5.00"]
    assert rows[1][0] == "'\tcmd"
    assert rows[1][2] == "'\r@cmd"


def test_safe_cells_are_not_prefixed(admin_user, thing):
    action = make_csv_export_action(fields=("name", "name_ar", "reference"))
    assert table(run(action, plain_admin(), admin_user))[1] == [
        "Deep Learning",
        "التعلم العميق",
        "978-0-262-03561-3",
    ]


def test_bidi_controls_are_stripped_from_values(admin_user):
    controls = "".join(sorted(BIDI_CONTROL_CHARS))
    Thing.objects.create(name=f"مرحبا{controls}v1.2.3", reference=f"{controls}978-0-13")
    action = make_csv_export_action(fields=("name", "reference"))
    data = raw_bytes(run(action, plain_admin(), admin_user))
    text = data.decode("utf-8-sig")
    assert not any(char in text for char in BIDI_CONTROL_CHARS)
    assert list(csv.reader(io.StringIO(text)))[1:] == [["مرحباv1.2.3", "978-0-13"]]


def test_html_display_values_become_plain_text(admin_user, thing):
    def badge(obj):
        return format_html("<b>{}</b>", "نص & مال")

    badge.short_description = "شارة"
    action = make_csv_export_action(fields=(badge,))
    assert table(run(action, plain_admin(), admin_user))[1] == ["نص & مال"]


def test_html_protocol_values_become_plain_text(admin_user, thing):
    class Html:
        def __html__(self):
            return "<i>مال &amp; أعمال</i>"

    def column(obj):
        return Html()

    column.short_description = "غلاف"
    action = make_csv_export_action(fields=(column,))
    assert table(run(action, plain_admin(), admin_user))[1] == ["مال & أعمال"]


def test_callable_objects_and_unknown_names(admin_user, thing):
    class Column:
        short_description = "عمود"

        def __call__(self, obj):
            return obj.quantity

    action = make_csv_export_action(fields=(Column(), "nonexistent"))
    assert table(run(action, plain_admin(), admin_user)) == [
        ["عمود", "nonexistent"],
        ["1234", ""],
    ]
    action = make_csv_export_action(fields=(Column(),), header="name")
    assert table(run(action, plain_admin(), admin_user))[1] == ["1234"]


def test_display_method_errors_become_empty_cells(admin_user, thing):
    class BrokenAdmin(admin.ModelAdmin):
        list_display = ("broken",)

        @admin.display(description="معطوب")
        def broken(self, obj):
            raise ObjectDoesNotExist

    modeladmin = BrokenAdmin(Thing, AdminSite())
    assert table(run(export_as_csv, modeladmin, admin_user))[1] == [""]


# -- dates, times and time zones ----------------------------------------------------


def test_dates_and_datetimes_are_iso_8601_in_the_current_zone(admin_user):
    Book.objects.create(
        title="مقدمة ابن خلدون",
        isbn="978-9953-0-0001-1",
        published_on=date(2024, 3, 5),
        available_from=datetime(2025, 1, 1, 9, 30, tzinfo=dt_timezone.utc),
        launch_time=time(18, 45),
    )
    action = make_csv_export_action(fields=("published_on", "available_from", "launch_time"))
    modeladmin = plain_admin(Book)
    with timezone.override("Asia/Riyadh"):
        response = run(action, modeladmin, admin_user)
    # Consumed outside the override: the generator kept the request time zone.
    assert table(response)[1] == ["2024-03-05", "2025-01-01T12:30:00+03:00", "18:45:00"]
    with timezone.override("UTC"):
        response = run(action, modeladmin, admin_user)
    assert table(response)[1] == ["2024-03-05", "2025-01-01T09:30:00+00:00", "18:45:00"]


def test_naive_datetimes_are_left_untouched(admin_user, thing):
    def naive(obj):
        return datetime(2025, 1, 1, 9, 30)

    action = make_csv_export_action(fields=(naive,))
    assert table(run(action, plain_admin(), admin_user))[1] == ["2025-01-01T09:30:00"]


@override_settings(USE_TZ=False)
def test_aware_datetimes_without_use_tz_keep_their_offset(admin_user, thing):
    def aware(obj):
        return datetime(2025, 1, 1, 9, 30, tzinfo=dt_timezone.utc)

    action = make_csv_export_action(fields=(aware,))
    assert table(run(action, plain_admin(), admin_user))[1] == ["2025-01-01T09:30:00+00:00"]


def test_none_values_become_empty_cells(admin_user):
    Book.objects.create(title="بلا تاريخ", isbn="978-0-00-000000-0")
    action = make_csv_export_action(fields=("published_on", "available_from", "category"))
    assert table(run(action, plain_admin(Book), admin_user))[1] == ["", "", ""]


# -- related fields and choices ------------------------------------------------------


def test_choices_use_their_display_value(admin_user):
    Book.objects.create(title="كتاب", isbn="978-0-00-000000-1", status="published")
    action = make_csv_export_action(fields=("status",))
    assert table(run(action, plain_admin(Book), admin_user))[1] == ["Published"]


def test_foreign_keys_and_related_lookups(admin_user):
    history = Category.objects.create(name="تاريخ")
    Book.objects.create(title="مقدمة ابن خلدون", isbn="978-9953-0-0001-1", category=history)
    Book.objects.create(title="بلا تصنيف", isbn="978-0-00-000000-2")
    action = make_csv_export_action(fields=("category", "category__name"))
    response = run(action, plain_admin(Book), admin_user, Book.objects.order_by("pk"))
    assert table(response)[1:] == [
        ["تاريخ", "تاريخ"],
        ["", ""],
    ]


def test_related_path_walks_callables_and_tolerates_bad_paths(admin_user, thing):
    # A path may traverse a property and a callable attribute; the walker calls
    # the callable and still resolves a value even when no model field matches.
    action = make_csv_export_action(fields=("slug__upper",))
    assert table(run(action, plain_admin(), admin_user))[1] == ["DEEP-LEARNING"]
    # A missing attribute anywhere in the path yields an empty cell, not an error.
    action = make_csv_export_action(fields=("slug__nonexistent",))
    assert table(run(action, plain_admin(), admin_user))[1] == [""]


# -- BOM and delimiter -----------------------------------------------------------------


def test_bom_can_be_disabled(admin_user, thing):
    action = make_csv_export_action(fields=("name",), bom=False)
    data = raw_bytes(run(action, plain_admin(), admin_user))
    assert not data.startswith(BOM)
    assert data.decode("utf-8").startswith("name\r\n")


def test_delimiter_option(admin_user, thing):
    action = make_csv_export_action(fields=("name", "quantity"), delimiter=";")
    data = raw_bytes(run(action, plain_admin(), admin_user)).decode("utf-8-sig")
    assert data.splitlines() == ["name;quantity", "Deep Learning;1234"]


def test_values_containing_the_delimiter_are_quoted(admin_user):
    Thing.objects.create(name="كتب، وأوراق", quantity=3)
    action = make_csv_export_action(fields=("name", "quantity"))
    assert table(run(action, plain_admin(), admin_user))[1] == ["كتب، وأوراق", "3"]


# -- option validation -------------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {"digits": "arab"},
        {"digits": ""},
        {"header": "pretty"},
        {"delimiter": ";;"},
        {"delimiter": ""},
        {"delimiter": 9},
    ],
)
def test_invalid_options_are_rejected(kwargs):
    with pytest.raises(ValueError):
        make_csv_export_action(**kwargs)


# -- permissions ---------------------------------------------------------------------------


def test_anonymous_user_is_denied(thing):
    request = RequestFactory().post(URL)
    request.user = AnonymousUser()
    with pytest.raises(PermissionDenied):
        export_as_csv(plain_admin(), request, Thing.objects.all())


def test_staff_without_view_permission_is_denied(thing, django_user_model):
    user = django_user_model.objects.create_user(username="staff", password="pw", is_staff=True)
    with pytest.raises(PermissionDenied):
        run(export_as_csv, plain_admin(), user)


def test_view_permission_is_enough(thing, django_user_model):
    user = django_user_model.objects.create_user(username="viewer", password="pw", is_staff=True)
    user.user_permissions.add(Permission.objects.get(codename="view_thing"))
    response = run(export_as_csv, plain_admin(), user)
    assert response.streaming
    assert table(response)[1] == ["Deep Learning"]


def test_change_permission_implies_view(thing, django_user_model):
    user = django_user_model.objects.create_user(username="editor", password="pw", is_staff=True)
    user.user_permissions.add(Permission.objects.get(codename="change_thing"))
    assert run(export_as_csv, plain_admin(), user).streaming


# -- streaming --------------------------------------------------------------------------------


def test_50000_rows_stream_through_iterator(admin_user, monkeypatch):
    Thing.objects.bulk_create(
        [Thing(name=f"عنصر {index}", quantity=index) for index in range(50_000)]
    )
    calls = []
    original = QuerySet.iterator

    def spy(self, *args, **kwargs):
        calls.append((args, kwargs))
        return original(self, *args, **kwargs)

    monkeypatch.setattr(QuerySet, "iterator", spy)
    action = make_csv_export_action(fields=("name", "quantity"))
    response = run(action, plain_admin(), admin_user)
    assert response.streaming
    # Nothing has been fetched yet: the body is a lazy stream.
    assert calls == []
    chunks = iter(response.streaming_content)
    assert next(chunks) == BOM
    assert next(chunks) == b"name,quantity\r\n"
    first_row = next(chunks)
    assert calls == [((), {"chunk_size": 2000})]
    assert first_row == "عنصر 0,0\r\n".encode()
    count = 3 + sum(1 for _ in chunks)
    assert count == 50_002  # BOM + header + one chunk per row
    assert calls == [((), {"chunk_size": 2000})]
