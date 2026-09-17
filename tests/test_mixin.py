"""``BidiSafeAdminMixin`` applied to a real changelist."""

import pytest
from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, override_settings

from django_rtl_admin import BidiSafeAdminMixin
from django_rtl_admin.bidi import FSI, PDI

from .testapp.models import Thing

pytestmark = pytest.mark.django_db

ARABIC = "التعلم"
CHANGELIST_URL = "/admin/testapp/thing/"


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


def test_delete_confirmation_isolates_the_object_name(admin_client, thing):
    response = admin_client.get(
        f"/admin/testapp/thing/{thing.pk}/delete/",
        headers={"accept-language": "ar-eg"},
    )
    assert response.status_code == 200
    html = response.content.decode()
    assert FSI + thing.name + PDI in html


def test_delete_success_message_isolates_the_object_name(admin_client, thing):
    delete_url = f"/admin/testapp/thing/{thing.pk}/delete/"
    response = admin_client.post(
        delete_url,
        {"post": "yes"},
        headers={"accept-language": "ar-eg"},
        follow=True,
    )
    assert response.status_code == 200
    html = response.content.decode()
    assert FSI + thing.name + PDI in html
    assert not Thing.objects.filter(pk=thing.pk).exists()


def test_html_in_object_name_stays_escaped_on_delete_confirmation(admin_client):
    thing = Thing.objects.create(name="<script>alert(1)</script>", reference="x")
    html = admin_client.get(f"/admin/testapp/thing/{thing.pk}/delete/").content.decode()
    assert "<script>alert(1)</script>" not in html
    assert "<script>alert(1)</script>" in html


def test_stylesheet_isolates_message_list_links():
    from pathlib import Path

    import django_rtl_admin

    css_path = (
        Path(django_rtl_admin.__file__).resolve().parent
        / "static"
        / "django_rtl_admin"
        / "css"
        / "rtl-admin.css"
    )
    css = css_path.read_text(encoding="utf-8")
    assert "ul.messagelist a" in css
    assert "unicode-bidi: isolate;" in css
