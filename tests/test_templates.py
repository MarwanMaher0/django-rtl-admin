"""Template overrides, the rendered admin shell and the language switcher."""

import os

import django
import pytest
from django.template.loader import get_template
from django.test import override_settings

pytestmark = pytest.mark.django_db

# Django spells the native Arabic name with a shadda.
ARABIC_NATIVE = "\u0627\u0644\u0639\u0631\u0628\u064a\u0651\u0629"

INDEX_URL = "/admin/"


# -- override resolution ---------------------------------------------------


def test_base_site_resolves_to_this_app_and_not_to_contrib_admin():
    template = get_template("admin/base_site.html")
    origin = template.origin.name
    assert os.path.join("django_rtl_admin", "templates", "admin", "base_site.html") in origin
    assert os.path.join("contrib", "admin", "templates") not in origin


def test_tabular_inline_resolves_to_this_app_and_not_to_contrib_admin():
    template = get_template("admin/edit_inline/tabular.html")
    origin = template.origin.name
    assert os.path.join("django_rtl_admin", "templates", "admin", "edit_inline") in origin
    assert os.path.join("contrib", "admin", "templates") not in origin


def test_changelist_results_resolve_to_this_app_and_not_to_contrib_admin():
    template = get_template("admin/change_list_results.html")
    origin = template.origin.name
    assert os.path.join("django_rtl_admin", "templates", "admin") in origin
    assert os.path.join("contrib", "admin", "templates") not in origin


def test_split_datetime_resolves_to_this_app_and_not_to_contrib_admin():
    template = get_template("admin/widgets/split_datetime.html")
    origin = template.origin.name
    assert os.path.join("django_rtl_admin", "templates", "admin", "widgets") in origin
    assert os.path.join("contrib", "admin", "templates") not in origin


def test_contrib_base_html_is_not_shadowed():
    origin = get_template("admin/base.html").origin.name
    assert os.path.join("contrib", "admin", "templates") in origin


def test_the_reusable_base_site_is_importable_on_its_own():
    template = get_template("django_rtl_admin/base_site.html")
    assert "django_rtl_admin" in template.origin.name


def test_admin_base_site_only_extends_the_reusable_template():
    source = open(get_template("admin/base_site.html").origin.name, encoding="utf-8").read()
    assert source.lstrip().startswith('{% extends "django_rtl_admin/base_site.html" %}')


# -- rendered shell --------------------------------------------------------


def test_admin_page_links_the_stylesheet(admin_client):
    html = admin_client.get(INDEX_URL).content.decode()
    assert "django_rtl_admin/css/rtl-admin.css" in html


def test_the_stylesheet_is_linked_after_the_contrib_rtl_stylesheet(admin_client):
    html = admin_client.get(INDEX_URL, headers={"accept-language": "ar"}).content.decode()
    assert html.index("django_rtl_admin/css/rtl-admin.css") > html.index("admin/css/responsive.css")


def test_the_viewport_allows_pinch_zoom(admin_client):
    html = admin_client.get(INDEX_URL).content.decode()
    assert html.count('name="viewport"') == 1
    assert '<meta name="viewport" content="width=device-width, initial-scale=1.0">' in html
    assert "user-scalable=no" not in html
    assert "maximum-scale" not in html


@override_settings(RTL_ADMIN={"ENABLE_CSS": False})
def test_the_stylesheet_can_be_turned_off(admin_client):
    html = admin_client.get(INDEX_URL).content.decode()
    assert "django_rtl_admin/css/rtl-admin.css" not in html


def test_body_carries_the_direction_class(admin_client):
    html = admin_client.get(INDEX_URL).content.decode()
    assert "rtl-admin rtl-admin--ltr" in html


def test_body_flips_to_rtl_for_an_rtl_language(admin_client):
    html = admin_client.get(INDEX_URL, headers={"accept-language": "ar"}).content.decode()
    assert "rtl-admin--rtl" in html
    assert 'dir="rtl"' in html


def test_the_branding_block_is_preserved(admin_client):
    html = admin_client.get(INDEX_URL).content.decode()
    assert 'id="site-name"' in html
    assert "Django administration" in html
    expected_tag = "h1" if django.VERSION < (5, 0) else "div"
    assert f'<{expected_tag} id="site-name">' in html


def test_the_page_title_block_is_preserved(admin_client):
    html = admin_client.get(INDEX_URL).content.decode()
    assert "<title>" in html
    assert "Django site admin" in html


def test_the_admin_still_renders_its_own_content(admin_client):
    html = admin_client.get(INDEX_URL).content.decode()
    assert "Site administration" in html


def test_changelist_action_checkboxes_have_accessible_names(admin_client):
    from tests.testapp.models import Thing

    Thing.objects.create(name="Alpha")
    html = admin_client.get("/admin/testapp/thing/").content.decode()
    assert 'aria-label="Select all objects on this page for an action"' in html
    assert 'aria-label="Select this object for an action - Alpha"' in html


def test_changelist_action_checkbox_names_are_translated_into_arabic(admin_client):
    from tests.testapp.models import Thing

    Thing.objects.create(name="ألفا")
    html = admin_client.get("/admin/testapp/thing/", headers={"accept-language": "ar"}).content.decode()
    assert 'aria-label="تحديد جميع العناصر في هذه الصفحة لتنفيذ إجراء"' in html
    assert 'aria-label="تحديد هذا العنصر لتنفيذ إجراء - ألفا"' in html


# -- language switcher -----------------------------------------------------


def test_the_switcher_lists_every_configured_language(admin_client):
    html = admin_client.get(INDEX_URL).content.decode()
    assert 'class="rtl-admin-language-switcher"' in html
    assert 'aria-label="Language"' in html
    for code in ("en", "ar", "ar-eg", "he"):
        assert f'value="{code}"' in html


def test_the_switcher_posts_to_set_language_and_keeps_the_current_url(admin_client):
    html = admin_client.get("/admin/testapp/thing/").content.decode()
    assert 'action="/i18n/setlang/"' in html
    assert 'name="next" value="/admin/testapp/thing/"' in html
    assert 'name="csrfmiddlewaretoken"' in html


def test_the_switcher_marks_the_active_language(admin_client):
    html = admin_client.get(INDEX_URL, headers={"accept-language": "ar"}).content.decode()
    assert '<option value="ar" lang="ar" dir="rtl" selected>' in html


def test_the_switcher_appears_on_the_login_page(client):
    html = client.get("/admin/login/").content.decode()
    assert 'class="rtl-admin-language-switcher"' in html


@override_settings(RTL_ADMIN={"LANGUAGE_SWITCHER": False})
def test_the_switcher_can_be_turned_off(admin_client):
    html = admin_client.get(INDEX_URL).content.decode()
    assert "rtl-admin-language-switcher" not in html


@override_settings(LANGUAGES=[("en", "English")])
def test_the_switcher_hides_itself_with_a_single_language(admin_client):
    html = admin_client.get(INDEX_URL).content.decode()
    assert "rtl-admin-language-switcher" not in html


@override_settings(ROOT_URLCONF="tests.urls_without_i18n")
def test_the_switcher_hides_itself_when_set_language_is_not_routed(admin_client):
    html = admin_client.get(INDEX_URL).content.decode()
    assert "rtl-admin-language-switcher" not in html


@override_settings(RTL_ADMIN={"LANGUAGE_SWITCHER_LANGUAGES": [("en", "English"), ("ar", "Arabic")]})
def test_the_switcher_language_list_can_be_overridden(admin_client):
    html = admin_client.get(INDEX_URL).content.decode()
    assert 'value="ar"' in html
    assert 'value="he"' not in html


@override_settings(RTL_ADMIN={"LANGUAGE_SWITCHER_LABELS": "both"})
def test_the_switcher_can_show_native_and_translated_names(admin_client):
    html = admin_client.get(INDEX_URL).content.decode()
    assert ARABIC_NATIVE in html
    assert "Arabic" in html


def test_the_switcher_shows_native_names_by_default(admin_client):
    html = admin_client.get(INDEX_URL).content.decode()
    assert ARABIC_NATIVE in html


def test_switching_the_language_actually_changes_the_admin(admin_client):
    response = admin_client.post("/i18n/setlang/", {"language": "ar", "next": "/admin/"}, follow=True)
    assert response.status_code == 200
    assert 'dir="rtl"' in response.content.decode()


def test_the_switcher_label_is_translated(admin_client):
    html = admin_client.get(INDEX_URL, headers={"accept-language": "ar"}).content.decode()
    assert "اللغة" in html
