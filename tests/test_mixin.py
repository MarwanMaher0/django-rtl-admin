"""``BidiSafeAdminMixin`` applied to a real changelist."""

import django
import pytest
from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, override_settings

from django_rtl_admin import BidiSafeAdminMixin
from django_rtl_admin.bidi import FSI, PDI

from .testapp.models import Book, Category, Thing

pytestmark = pytest.mark.django_db

ARABIC = "التعلم"
CHANGELIST_URL = "/admin/testapp/thing/"
BOOK_CHANGELIST_URL = "/admin/testapp/book/"


def make_admin(**attrs):
    cls = type("TempAdmin", (BidiSafeAdminMixin, admin.ModelAdmin), attrs)
    return cls(Thing, AdminSite())


def request_for(user):
    request = RequestFactory().get(CHANGELIST_URL)
    request.user = user
    return request


# -- list_display rewriting ------------------------------------------------


def test_list_display_entries_become_isolating_wrappers(admin_user):
    model_admin = make_admin(list_display=("name", "reference"))
    display = model_admin.get_list_display(request_for(admin_user))
    assert all(callable(entry) for entry in display)
    assert [entry.__name__ for entry in display] == ["name", "reference"]


def test_wrappers_keep_the_column_labels(admin_user):
    model_admin = make_admin(list_display=("name", "reference"))
    display = model_admin.get_list_display(request_for(admin_user))
    assert [str(entry.short_description) for entry in display] == ["name", "reference"]


def test_wrappers_keep_the_sort_field(admin_user):
    model_admin = make_admin(list_display=("name",))
    (wrapper,) = model_admin.get_list_display(request_for(admin_user))
    assert wrapper.admin_order_field == "name"


def test_wrappers_are_cached_so_identity_is_stable(admin_user):
    model_admin = make_admin(list_display=("name",))
    request = request_for(admin_user)
    assert model_admin.get_list_display(request) == model_admin.get_list_display(request)


def test_list_display_links_are_translated_to_the_same_wrappers(admin_user):
    model_admin = make_admin(list_display=("name", "reference"), list_display_links=("reference",))
    request = request_for(admin_user)
    display = model_admin.get_list_display(request)
    links = model_admin.get_list_display_links(request, display)
    assert links[0] is display[1]


def test_sortable_by_is_translated_too(admin_user):
    model_admin = make_admin(list_display=("name", "reference"), sortable_by=("name",))
    request = request_for(admin_user)
    display = model_admin.get_list_display(request)
    assert model_admin.get_sortable_by(request)[0] is display[0]


def test_boolean_columns_are_left_alone(admin_user):
    model_admin = make_admin(list_display=("name", "is_active"))
    display = model_admin.get_list_display(request_for(admin_user))
    assert display[1] == "is_active"


def test_list_editable_columns_are_left_alone(admin_user):
    model_admin = make_admin(
        list_display=("name", "reference"), list_display_links=("name",), list_editable=("reference",)
    )
    display = model_admin.get_list_display(request_for(admin_user))
    assert display[1] == "reference"


def test_excluded_columns_are_left_alone(admin_user):
    model_admin = make_admin(list_display=("name", "reference"), bidi_isolate_exclude=("reference",))
    display = model_admin.get_list_display(request_for(admin_user))
    assert display[1] == "reference"


def test_bidi_isolate_fields_restricts_the_set(admin_user):
    model_admin = make_admin(list_display=("name", "reference"), bidi_isolate_fields=("reference",))
    display = model_admin.get_list_display(request_for(admin_user))
    assert display[0] == "name"
    assert callable(display[1])


def test_the_mixin_can_be_switched_off_per_admin(admin_user):
    model_admin = make_admin(list_display=("name",), bidi_isolate_changelist=False)
    assert model_admin.get_list_display(request_for(admin_user)) == ("name",)


@override_settings(RTL_ADMIN={"ISOLATE_CHANGELIST": False})
def test_the_mixin_can_be_switched_off_globally(admin_user):
    model_admin = make_admin(list_display=("name",))
    assert model_admin.get_list_display(request_for(admin_user)) == ("name",)


def test_callables_already_in_list_display_are_passed_through(admin_user):
    def custom(obj):
        return obj.name

    model_admin = make_admin(list_display=(custom,))
    assert model_admin.get_list_display(request_for(admin_user)) == (custom,)


# -- rendered output -------------------------------------------------------


def test_changelist_cells_are_isolated(admin_client, thing):
    response = admin_client.get(CHANGELIST_URL)
    assert response.status_code == 200
    html = response.content.decode()
    assert FSI + "978-0-262-03561-3" + PDI in html
    assert FSI + thing.name_ar + PDI in html


def test_changelist_keeps_the_admin_column_css_classes(admin_client, thing):
    html = admin_client.get(CHANGELIST_URL).content.decode()
    assert 'class="field-reference"' in html
    assert "column-reference" in html


def test_changelist_keeps_the_sort_links(admin_client, thing):
    html = admin_client.get(CHANGELIST_URL).content.decode()
    assert "sortable column-name" in html


def test_changelist_keeps_the_link_to_the_change_form(admin_client, thing):
    html = admin_client.get(CHANGELIST_URL).content.decode()
    assert f'href="/admin/testapp/thing/{thing.pk}/change/"' in html


def test_changelist_still_renders_the_boolean_icon(admin_client, thing):
    html = admin_client.get(CHANGELIST_URL).content.decode()
    assert "icon-yes" in html


def test_html_in_a_value_stays_escaped_in_the_changelist(admin_client):
    Thing.objects.create(name="<script>alert(1)</script>", reference="x")
    html = admin_client.get(CHANGELIST_URL).content.decode()
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_an_empty_value_is_not_isolated(admin_client):
    Thing.objects.create(name="Empty", reference="")
    html = admin_client.get(CHANGELIST_URL).content.decode()
    assert FSI + PDI not in html


def test_a_custom_display_method_is_isolated_too(admin_client, thing):
    html = admin_client.get(CHANGELIST_URL).content.decode()
    assert FSI + "DEEP LEARNING" + PDI in html


def test_sorting_by_an_isolated_column_still_works(admin_client, thing):
    Thing.objects.create(name="Alpha", reference="a")
    response = admin_client.get(CHANGELIST_URL, {"o": "1"})
    assert response.status_code == 200
    names = [obj.name for obj in response.context["cl"].result_list]
    assert names == sorted(names)


def test_searching_still_works(admin_client, thing):
    response = admin_client.get(CHANGELIST_URL, {"q": "978-0-262"})
    assert response.status_code == 200
    assert response.context["cl"].result_count == 1


# -- related lookups ---------------------------------------------------------

related_lookups = pytest.mark.skipif(
    django.VERSION < (5, 1), reason="list_display accepts related lookups on Django 5.1+"
)


def make_book_admin(**attrs):
    attrs.setdefault("actions", None)
    cls = type("TempBookAdmin", (BidiSafeAdminMixin, admin.ModelAdmin), attrs)
    return cls(Book, admin.site)


def render_book_changelist(model_admin, user, **params):
    request = RequestFactory().get(BOOK_CHANGELIST_URL, params)
    request.user = user
    response = model_admin.changelist_view(request)
    response.render()
    return response


@pytest.fixture
def books(db):
    zeta = Category.objects.create(name="Zeta", is_featured=True)
    alpha = Category.objects.create(name="Alpha")
    middle = Category.objects.create(name=ARABIC)
    Book.objects.create(title="A first", isbn="1", category=zeta)
    Book.objects.create(title="B second", isbn="2", category=alpha)
    Book.objects.create(title="C third", isbn="3", category=middle)
    Book.objects.create(title="D fourth", isbn="4", category=None)


@related_lookups
def test_a_related_lookup_keeps_its_sort_field(admin_user):
    model_admin = make_book_admin(list_display=("title", "category__name"))
    display = model_admin.get_list_display(request_for(admin_user))
    assert display[1].__name__ == "category__name"
    assert display[1].admin_order_field == "category__name"


@related_lookups
def test_a_related_lookup_column_has_a_sort_link(admin_user, books):
    model_admin = make_book_admin(list_display=("title", "category__name"))
    html = render_book_changelist(model_admin, admin_user).content.decode()
    assert "sortable column-category__name" in html
    assert 'class="field-category__name"' in html


@related_lookups
@pytest.mark.parametrize(("order", "reverse"), [("1", False), ("-1", True)])
def test_sorting_by_a_related_lookup_orders_the_rows(admin_user, books, order, reverse):
    model_admin = make_book_admin(list_display=("title", "category__name"))
    response = render_book_changelist(model_admin, admin_user, o=order)
    assert response.status_code == 200
    names = [
        book.category.name
        for book in response.context_data["cl"].result_list
        if book.category is not None
    ]
    assert names == sorted(names, reverse=reverse)
    assert len(names) == 3


@related_lookups
def test_a_related_lookup_value_is_isolated(admin_user, books):
    model_admin = make_book_admin(list_display=("title", "category__name"))
    html = render_book_changelist(model_admin, admin_user).content.decode()
    assert FSI + "Alpha" + PDI in html
    assert FSI + ARABIC + PDI in html
    assert FSI + PDI not in html


@related_lookups
def test_a_boolean_field_at_the_end_of_a_lookup_is_left_alone(admin_user, books):
    model_admin = make_book_admin(list_display=("title", "category__is_featured"))
    display = model_admin.get_list_display(request_for(admin_user))
    assert display[1] == "category__is_featured"
    response = render_book_changelist(model_admin, admin_user)
    assert response.status_code == 200


@pytest.mark.skipif(django.VERSION >= (5, 1), reason="behaviour before Django 5.1")
def test_a_related_lookup_is_not_resolved_before_django_5_1(admin_user):
    model_admin = make_book_admin(list_display=("title", "category__name"))
    assert model_admin._bidi_model_field("category__name") is None
    assert model_admin._bidi_order_field("category__name", None, None) is None
    with pytest.raises(AttributeError, match="Unable to lookup 'category__name'"):
        model_admin.get_list_display(request_for(admin_user))
