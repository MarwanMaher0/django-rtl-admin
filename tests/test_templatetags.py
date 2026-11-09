"""Template filter and tag registration and rendering."""

import datetime

import pytest
from django.template import Context, Template, engines
from django.template.library import InvalidTemplateLibrary
from django.test import override_settings
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.translation import override as override_language

from django_rtl_admin import formatting
from django_rtl_admin.bidi import FSI, LRI, PDI, RLI
from django_rtl_admin.formatting import DIGITS
from django_rtl_admin.templatetags import rtl_admin as tags

ARABIC = "مرحبا"

EXPECTED_FILTERS = {
    "bidi_isolate",
    "bidi_runs",
    "bidi_strip",
    "bidi_dir",
    "l10n_number",
    "l10n_currency",
    "l10n_percent",
    "l10n_date",
    "l10n_datetime",
    "l10n_time",
    "local_digits",
    "rtl_admin_accessible_viewport",
    "rtl_admin_result_object",
    "rtl_admin_action_label",
}

EXPECTED_TAGS = {
    "rtl_admin_direction",
    "rtl_admin_body_class",
    "rtl_admin_site_name_tag",
    "rtl_admin_styles",
    "rtl_admin_scripts",
    "rtl_admin_language_switcher",
    "rtl_admin_language_links",
    "rtl_admin_isolated_join",
}


def render(template, **context):
    return Template("{% load rtl_admin %}" + template).render(Context(context))


def test_the_library_is_loadable_by_name():
    engine = engines["django"]
    try:
        library = engine.engine.template_libraries["rtl_admin"]
    except KeyError:  # pragma: no cover - only if discovery breaks
        raise AssertionError("rtl_admin template library is not discoverable") from None
    assert library is not None


def test_every_documented_filter_is_registered():
    assert EXPECTED_FILTERS <= set(tags.register.filters)


def test_every_documented_tag_is_registered():
    assert EXPECTED_TAGS <= set(tags.register.tags)


def test_loading_the_library_does_not_raise():
    try:
        Template("{% load rtl_admin %}")
    except InvalidTemplateLibrary as exc:  # pragma: no cover
        raise AssertionError(str(exc)) from exc


# -- bidi filters ----------------------------------------------------------


def test_bidi_isolate_filter_wraps_the_value():
    assert render("{{ v|bidi_isolate }}", v="abc") == FSI + "abc" + PDI


def test_bidi_isolate_filter_takes_a_direction():
    assert render('{{ v|bidi_isolate:"ltr" }}', v="abc") == LRI + "abc" + PDI
    assert render('{{ v|bidi_isolate:"rtl" }}', v="abc") == RLI + "abc" + PDI


def test_bidi_isolate_filter_escapes_html():
    output = render("{{ v|bidi_isolate }}", v="<script>x</script>")
    assert "<script>" not in output
    assert "&lt;script&gt;" in output


def test_bidi_isolate_filter_does_not_double_escape():
    output = render("{{ v|bidi_isolate }}", v="a & b")
    assert output.count("&amp;") == 1


def test_bidi_isolate_filter_respects_autoescape_off():
    output = render("{% autoescape off %}{{ v|bidi_isolate }}{% endautoescape %}", v="<b>")
    assert output == FSI + "<b>" + PDI


def test_bidi_runs_filter():
    output = render('{{ v|bidi_runs:"rtl" }}', v=f"{ARABIC} v1.0")
    assert LRI + "v1.0" + PDI in output


def test_bidi_runs_filter_escapes_html():
    output = render('{{ v|bidi_runs:"rtl" }}', v="<b>x</b>")
    assert "<b>" not in output


def test_bidi_strip_filter():
    assert render("{{ v|bidi_strip }}", v=FSI + "abc" + PDI) == "abc"


@pytest.mark.parametrize(("value", "expected"), [("abc", "ltr"), (ARABIC, "rtl"), ("", "ltr")])
def test_bidi_dir_filter(value, expected):
    assert render("{{ v|bidi_dir }}", v=value) == expected


# -- l10n filters ----------------------------------------------------------


def test_l10n_number_filter_uses_the_active_locale():
    with override_language("ar-eg"):
        output = render("{{ v|l10n_number }}", v=1234)
    assert any(char in output for char in DIGITS["arab"])


def test_l10n_number_filter_accepts_decimal_positions():
    with override_language("en"):
        assert render('{{ v|l10n_number:"2" }}', v=2.5) == "2.50"


def test_l10n_currency_filter():
    with override_language("en"):
        output = render('{{ v|l10n_currency:"USD" }}', v=10)
    assert "10" in output


def test_l10n_date_filter():
    with override_language("en"):
        output = render("{{ v|l10n_date }}", v=datetime.date(2024, 3, 5))
    assert "2024" in output


def test_l10n_datetime_and_time_filters():
    value = datetime.datetime(2024, 3, 5, 14, 30)
    with override_language("en"):
        assert "2024" in render("{{ v|l10n_datetime }}", v=value)
        assert render("{{ v|l10n_time }}", v=value.time()) != ""


def test_l10n_datetime_and_time_filters_declare_expects_localtime():
    assert getattr(tags.register.filters["l10n_datetime"], "expects_localtime", False) is True
    assert getattr(tags.register.filters["l10n_time"], "expects_localtime", False) is True
    assert getattr(tags.register.filters["l10n_date"], "expects_localtime", False) is False


@pytest.mark.parametrize("use_babel", [True, False])
@pytest.mark.parametrize(
    ("language", "expected_day", "expected_time", "utc_time"),
    [
        ("en", "6", "12:30", "10:30"),
        ("ar-eg", "٦", "١٢:٣٠", "١٠:٣٠"),
    ],
)
def test_l10n_datetime_and_time_filters_respect_time_zone_and_timezone_override(
    monkeypatch, use_babel, language, expected_day, expected_time, utc_time
):
    if not use_babel:
        monkeypatch.setattr(formatting, "HAS_BABEL", False)
    value = datetime.datetime(2024, 3, 5, 22, 30, tzinfo=datetime.timezone.utc)
    with override_settings(USE_TZ=True, TIME_ZONE="Africa/Cairo"), override_language(language):
        dt_from_setting = render("{{ v|l10n_datetime }}", v=value)
        time_from_setting = render("{{ v|l10n_time }}", v=value)
    with timezone.override("Africa/Cairo"), override_language(language):
        dt_from_override = render("{{ v|l10n_datetime }}", v=value)
        time_from_override = render("{{ v|l10n_time }}", v=value)
    for dt_output in (dt_from_setting, dt_from_override):
        assert expected_day in dt_output
        assert expected_time in dt_output
        assert utc_time not in dt_output
    for time_output in (time_from_setting, time_from_override):
        assert expected_time in time_output
        assert utc_time not in time_output


@pytest.mark.parametrize("use_babel", [True, False])
@pytest.mark.parametrize(
    ("language", "expected_day", "expected_time", "cairo_time"),
    [
        ("en", "5", "10:30", "12:30"),
        ("ar-eg", "٥", "١٠:٣٠", "١٢:٣٠"),
    ],
)
def test_l10n_datetime_and_time_filters_respect_localtime_off_and_use_tz_false(
    monkeypatch, use_babel, language, expected_day, expected_time, cairo_time
):
    if not use_babel:
        monkeypatch.setattr(formatting, "HAS_BABEL", False)
    value = datetime.datetime(2024, 3, 5, 22, 30, tzinfo=datetime.timezone.utc)
    with (
        override_settings(USE_TZ=True, TIME_ZONE="Africa/Cairo"),
        override_language(language),
    ):
        dt_localtime_off = render(
            "{% load tz %}{% localtime off %}{{ v|l10n_datetime }}{% endlocaltime %}",
            v=value,
        )
        time_localtime_off = render(
            "{% load tz %}{% localtime off %}{{ v|l10n_time }}{% endlocaltime %}",
            v=value,
        )
    with (
        override_settings(USE_TZ=False, TIME_ZONE="Africa/Cairo"),
        override_language(language),
    ):
        dt_use_tz_false = render("{{ v|l10n_datetime }}", v=value)
        time_use_tz_false = render("{{ v|l10n_time }}", v=value)
    for dt_output in (dt_localtime_off, dt_use_tz_false):
        assert expected_day in dt_output
        assert expected_time in dt_output
        assert cairo_time not in dt_output
    for time_output in (time_localtime_off, time_use_tz_false):
        assert expected_time in time_output
        assert cairo_time not in time_output


@pytest.mark.parametrize("use_babel", [True, False])
def test_l10n_filters_leave_naive_values_and_plain_dates_untouched(monkeypatch, use_babel):
    if not use_babel:
        monkeypatch.setattr(formatting, "HAS_BABEL", False)
    naive_dt = datetime.datetime(2024, 3, 5, 22, 30)
    naive_time = datetime.time(22, 30)
    plain_date = datetime.date(2024, 3, 5)
    with (
        override_settings(USE_TZ=True, TIME_ZONE="Africa/Cairo"),
        timezone.override("Africa/Cairo"),
        override_language("en"),
    ):
        assert "5" in render("{{ v|l10n_datetime }}", v=naive_dt)
        assert "10:30" in render("{{ v|l10n_datetime }}", v=naive_dt)
        assert "10:30" in render("{{ v|l10n_time }}", v=naive_time)
        assert "5" in render("{{ v|l10n_date }}", v=plain_date)


def test_local_digits_filter():
    with override_language("ar-eg"):
        assert render("{{ v|local_digits }}", v="REF-2024") == "REF-٢٠٢٤"
    assert render("{{ v|local_digits }}", v=None) == ""


def test_accessible_viewport_filter_allows_zoom_without_changing_other_markup():
    html = '<meta name="viewport" content="user-scalable=no, width=device-width, initial-scale=1.0, maximum-scale=1.0"><link rel="stylesheet" href="responsive.css">'
    output = tags.rtl_admin_accessible_viewport(html)
    assert 'content="width=device-width, initial-scale=1.0"' in output
    assert "user-scalable" not in output
    assert '<link rel="stylesheet" href="responsive.css">' in output
    assert tags.rtl_admin_accessible_viewport(output) == output


def test_result_object_filter_selects_the_current_changelist_object():
    objects = ["first", "second"]
    assert tags.rtl_admin_result_object(objects, 1) == "second"


def test_action_label_filter_names_stock_checkboxes_and_escapes_object_text():
    cell = '<td class="action-checkbox"><input type="checkbox" name="_selected_action" value="1" class="action-select"></td>'
    with override_language("en"):
        output = tags.rtl_admin_action_label(mark_safe(cell), "<script>")
    assert 'aria-label="Select this object for an action - &lt;script&gt;"' in output
    assert tags.rtl_admin_action_label(output, "unused") == output
    assert tags.rtl_admin_action_label("<td>Title</td>", "unused") == "<td>Title</td>"


# -- tags ------------------------------------------------------------------


def test_direction_tag():
    with override_language("ar"):
        assert render("{% rtl_admin_direction %}") == "rtl"
    with override_language("en"):
        assert render("{% rtl_admin_direction %}") == "ltr"


def test_body_class_tag():
    with override_language("ar"):
        classes = render("{% rtl_admin_body_class %}").split()
    assert "rtl-admin" in classes
    assert "rtl-admin--rtl" in classes
    assert "rtl-admin--isolate-cells" in classes
    assert "rtl-admin--plaintext-fields" in classes


@override_settings(RTL_ADMIN={"ISOLATE_TABLE_CELLS": False, "PLAINTEXT_FORM_FIELDS": False})
def test_body_class_tag_drops_disabled_features():
    classes = render("{% rtl_admin_body_class %}").split()
    assert "rtl-admin--isolate-cells" not in classes
    assert "rtl-admin--plaintext-fields" not in classes


def test_styles_tag_links_the_stylesheet():
    output = render("{% rtl_admin_styles %}")
    assert "django_rtl_admin/css/rtl-admin.css" in output
    assert output.startswith("<link")


@override_settings(RTL_ADMIN={"ENABLE_CSS": False})
def test_styles_tag_can_be_turned_off():
    assert render("{% rtl_admin_styles %}") == ""


@override_settings(RTL_ADMIN={"FONT_STACK": '"Noto Naskh Arabic", serif'})
def test_font_stack_setting_is_emitted_as_a_custom_property():
    output = render("{% rtl_admin_styles %}")
    assert "--rtl-admin-font-stack" in output
    assert "Noto Naskh Arabic" in output


def test_scripts_tag():
    assert "language_switcher.js" in render("{% rtl_admin_scripts %}")


@override_settings(RTL_ADMIN={"LANGUAGE_SWITCHER": False})
def test_scripts_tag_is_silent_when_the_switcher_is_off():
    assert render("{% rtl_admin_scripts %}") == ""


def test_site_name_tag_matches_the_running_django():
    import django

    expected = "h1" if django.VERSION < (5, 0) else "div"
    assert render("{% rtl_admin_site_name_tag %}") == expected


def test_isolated_join_tag():
    output = render("{% rtl_admin_isolated_join values %}", values=["a", "<b>"])
    assert output == f"{FSI}a{PDI}, {FSI}&lt;b&gt;{PDI}"
    assert render("{% rtl_admin_isolated_join values %}", values=[]) == ""


def test_styles_and_scripts_carry_a_csp_nonce_when_one_is_available():
    # Django 6.0's CSP support puts a `csp_nonce` in the template context.
    context = Context({"csp_nonce": "abc123"})
    styles = Template("{% load rtl_admin %}{% rtl_admin_styles %}").render(context)
    scripts = Template("{% load rtl_admin %}{% rtl_admin_scripts %}").render(context)
    assert 'nonce="abc123"' in styles
    assert 'nonce="abc123"' in scripts


def test_styles_carry_no_nonce_attribute_without_csp():
    assert "nonce" not in render("{% rtl_admin_styles %}")
    assert "nonce" not in render("{% rtl_admin_scripts %}")
