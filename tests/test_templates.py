"""Template overrides, the rendered admin shell and the language switcher."""

import os
import re
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace

import django
import pytest
from django.template.loader import get_template
from django.test import override_settings

import django_rtl_admin

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


@pytest.mark.parametrize(("language", "direction"), [("en", "ltr"), ("ar-eg", "rtl")])
@pytest.mark.parametrize("enable_css", [True, False])
def test_body_carries_legacy_layout_classes_for_the_running_django(
    admin_client, language, direction, enable_css
):
    with override_settings(RTL_ADMIN={"ENABLE_CSS": enable_css}):
        response = admin_client.get(INDEX_URL, headers={"accept-language": language})
    assert response.status_code == 200
    body = re.search(r'<body\b[^>]*\bclass="([^"]*)"', response.content.decode())
    assert body is not None
    classes = body.group(1).split()
    assert "rtl-admin" in classes
    assert f"rtl-admin--{direction}" in classes
    assert "rtl-admin--isolate-cells" in classes
    assert "rtl-admin--plaintext-fields" in classes
    assert ("rtl-admin--pre-6-0" in classes) is (django.VERSION < (6, 0))
    assert ("rtl-admin--pre-6-1" in classes) is (django.VERSION < (6, 1))


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
    html = admin_client.get(
        "/admin/testapp/thing/", headers={"accept-language": "ar"}
    ).content.decode()
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
    response = admin_client.post(
        "/i18n/setlang/", {"language": "ar", "next": "/admin/"}, follow=True
    )
    assert response.status_code == 200
    assert 'dir="rtl"' in response.content.decode()


def test_the_switcher_label_is_translated(admin_client):
    html = admin_client.get(INDEX_URL, headers={"accept-language": "ar"}).content.decode()
    assert "اللغة" in html


# -- object names isolated by the stylesheet ---------------------------------

STYLESHEET = (
    Path(django_rtl_admin.__file__).parent / "static" / "django_rtl_admin" / "css" / "rtl-admin.css"
)
MESSAGE_LINK = ".rtl-admin--isolate-cells ul.messagelist li a"
# Up to Django 6.0 the subtitle is a child of #content; 6.1 wraps the titles.
SUBTITLE = (
    ".rtl-admin--isolate-cells #content > h2"
    if django.VERSION < (6, 1)
    else ".rtl-admin--isolate-cells #content > .titles-and-tools > .titles > h2"
)
DELETE_LIST_LINK = ".rtl-admin--isolate-cells.delete-confirmation #content ul li a"
OBJECT_NAME_SELECTORS = (
    MESSAGE_LINK,
    ".rtl-admin--isolate-cells #content > h2",
    ".rtl-admin--isolate-cells #content > .titles-and-tools > .titles > h2",
    DELETE_LIST_LINK,
)
OBJECT_NAME = "مقدمة 978-0-262-03561-3"
AR_EG = {"accept-language": "ar-eg"}


def isolating_selectors():
    """Every selector of a rule in rtl-admin.css that sets ``unicode-bidi: isolate``."""
    css = re.sub(r"/\*.*?\*/", "", STYLESHEET.read_text(encoding="utf-8"), flags=re.S)
    selectors = set()
    for selector_list, declarations in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        if re.search(r"unicode-bidi:\s*isolate\s*;", declarations):
            selectors.update(" ".join(selector.split()) for selector in selector_list.split(","))
    return selectors


class ElementPaths(HTMLParser):
    """Record every element of a page as its path from ``<html>`` down to itself."""

    VOID = frozenset("area base br col embed hr img input link meta source track wbr".split())

    def __init__(self, html):
        super().__init__()
        self.open = []
        self.paths = []
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set((attrs.get("class") or "").split())
        element = SimpleNamespace(tag=tag, id=attrs.get("id"), classes=classes, text="")
        self.paths.append([*self.open, element])
        if tag not in self.VOID:
            self.open.append(element)

    def handle_endtag(self, tag):
        for index in reversed(range(len(self.open))):
            if self.open[index].tag == tag:
                del self.open[index:]
                break

    def handle_data(self, data):
        if self.open:
            self.open[-1].text += data

    def named(self, tag, text):
        """Paths of the ``tag`` elements whose own text is ``text``."""
        return [
            path for path in self.paths if path[-1].tag == tag and path[-1].text.strip() == text
        ]


def selector_matches(selector, path):
    """Does ``selector`` match the last element of ``path``?

    Understands what the object-name rules use: tag, ``#id`` and ``.class``
    compounds joined by descendant and child combinators.
    """
    steps = re.findall(r">|[^\s>]+", selector)

    def compound_matches(compound, element):
        for token in re.findall(r"[#.]?[\w-]+", compound):
            if token.startswith("#"):
                if element.id != token[1:]:
                    return False
            elif token.startswith("."):
                if token[1:] not in element.classes:
                    return False
            elif element.tag != token:
                return False
        return True

    def matches(step, depth):
        if not compound_matches(steps[step], path[depth]):
            return False
        if step == 0:
            return True
        if steps[step - 1] == ">":
            return depth > 0 and matches(step - 2, depth - 1)
        return any(matches(step - 1, ancestor) for ancestor in range(depth))

    return matches(len(steps) - 1, len(path) - 1)


def matching_selectors(path):
    """The selectors under the cells switch, read from rtl-admin.css, that isolate ``path``."""
    return sorted(
        selector
        for selector in isolating_selectors()
        if selector.startswith(".rtl-admin--isolate-cells") and selector_matches(selector, path)
    )


def inside_content(paths):
    return [path for path in paths if any(element.id == "content" for element in path)]


@pytest.fixture
def named_thing(db):
    from tests.testapp.models import Thing

    return Thing.objects.create(name=OBJECT_NAME)


def test_the_stylesheet_isolates_object_names_under_the_cells_switch():
    assert set(OBJECT_NAME_SELECTORS) <= isolating_selectors()


def test_the_selector_matcher_tells_child_from_descendant():
    paths = ElementPaths(
        '<body class="a b"><div id="content"><h2>x</h2><div class="titles"><h2>y</h2></div></div>'
    )
    (direct,) = paths.named("h2", "x")
    (nested,) = paths.named("h2", "y")
    assert selector_matches(".a #content > h2", direct)
    assert not selector_matches(".a #content > h2", nested)
    assert selector_matches(".a.b #content h2", nested)
    assert selector_matches("#content > .titles > h2", nested)
    assert not selector_matches(".c #content h2", nested)
    assert not selector_matches(".a.c #content h2", nested)
    assert not selector_matches("#content > h1", direct)


def test_success_message_link_and_subtitle_match_the_object_name_selectors(
    admin_client, named_thing
):
    url = f"/admin/testapp/thing/{named_thing.pk}/change/"
    form = {"name": OBJECT_NAME, "quantity": "0", "price": "0", "_continue": "1"}
    response = admin_client.post(url, form, headers=AR_EG, follow=True)
    assert response.redirect_chain == [(url, 302)]
    paths = ElementPaths(response.content.decode())
    # The page quotes the name twice: in the message link and in the subtitle.
    (link,) = paths.named("a", OBJECT_NAME)
    assert matching_selectors(link) == [MESSAGE_LINK]
    (subtitle,) = paths.named("h2", OBJECT_NAME)
    assert matching_selectors(subtitle) == [SUBTITLE]


def test_add_message_link_matches_the_object_name_selector(admin_client):
    form = {"name": OBJECT_NAME, "quantity": "0", "price": "0"}
    response = admin_client.post("/admin/testapp/thing/add/", form, headers=AR_EG, follow=True)
    assert response.redirect_chain == [("/admin/testapp/thing/", 302)]
    paths = ElementPaths(response.content.decode())
    (link,) = [path for path in paths.named("a", OBJECT_NAME) if path[-2].tag == "li"]
    assert matching_selectors(link) == [MESSAGE_LINK]


def test_the_history_page_has_no_subtitle(admin_client, named_thing):
    """Django passes ``subtitle=None`` there; the name is part of the ``<h1>`` sentence."""
    url = f"/admin/testapp/thing/{named_thing.pk}/history/"
    response = admin_client.get(url, headers=AR_EG)
    assert response.context["subtitle"] is None
    paths = ElementPaths(response.content.decode())
    assert not paths.named("h2", OBJECT_NAME)
    (title,) = [path for path in inside_content(paths.paths) if path[-1].tag == "h1"]
    assert OBJECT_NAME in title[-1].text
    assert matching_selectors(title) == [".rtl-admin--isolate-cells #content h1"]


def test_delete_page_object_link_matches_the_object_name_selector(admin_client, named_thing):
    url = f"/admin/testapp/thing/{named_thing.pk}/delete/"
    paths = ElementPaths(admin_client.get(url, headers=AR_EG).content.decode())
    (link,) = inside_content(paths.named("a", OBJECT_NAME))
    assert matching_selectors(link) == [DELETE_LIST_LINK]


def test_delete_selected_page_object_link_matches_the_object_name_selector(
    admin_client, named_thing
):
    form = {"action": "delete_selected", "_selected_action": [str(named_thing.pk)]}
    response = admin_client.post("/admin/testapp/thing/", form, headers=AR_EG)
    assert response.status_code == 200
    assert "delete-selected-confirmation" in response.content.decode()
    paths = ElementPaths(response.content.decode())
    (link,) = inside_content(paths.named("a", OBJECT_NAME))
    assert matching_selectors(link) == [DELETE_LIST_LINK]


@override_settings(RTL_ADMIN={"ISOLATE_TABLE_CELLS": False})
def test_object_name_selectors_match_nothing_with_the_cells_switch_off(admin_client, named_thing):
    url = f"/admin/testapp/thing/{named_thing.pk}/change/"
    form = {"name": OBJECT_NAME, "quantity": "0", "price": "0", "_continue": "1"}
    pages = [
        admin_client.post(url, form, headers=AR_EG, follow=True),
        admin_client.get(f"/admin/testapp/thing/{named_thing.pk}/delete/", headers=AR_EG),
    ]
    for page in pages:
        paths = ElementPaths(page.content.decode())
        assert paths.named("a", OBJECT_NAME)
        assert not any(matching_selectors(path) for path in paths.paths)
