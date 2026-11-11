"""The system checks."""

from types import MappingProxyType

import pytest
from django.conf import settings
from django.contrib.admin.apps import AdminConfig
from django.core.checks import Error, Warning, run_checks
from django.test import override_settings

from django_rtl_admin import checks
from django_rtl_admin.apps import RTLAdminConfig
from django_rtl_admin.conf import CHOICES, DEFAULTS


class MyAdminConfig(AdminConfig):
    pass


class MyRTLAdminConfig(RTLAdminConfig):
    pass


def ids(warnings):
    return sorted(warning.id for warning in warnings)


def test_a_correct_installation_reports_nothing():
    assert checks.check_app_order(None) == []
    assert checks.check_settings_keys(None) == []
    assert checks.check_settings_values(None) == []
    assert checks.check_settings_types(None) == []
    assert checks.check_extra_rtl_languages_bidi(None) == []
    assert checks.check_language_switcher(None) == []


@override_settings(
    INSTALLED_APPS=[
        "django.contrib.admin",
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "django.contrib.sessions",
        "django.contrib.messages",
        "django_rtl_admin",
        "tests.testapp",
    ]
)
def test_the_app_order_is_checked():
    warnings = checks.check_app_order(None)
    assert ids(warnings) == ["rtl_admin.W001"]
    assert "INSTALLED_APPS" in warnings[0].msg


@pytest.mark.parametrize("rtl_first", [True, False])
@pytest.mark.parametrize("rtl_config", ["django_rtl_admin", "tests.test_checks.MyRTLAdminConfig"])
def test_the_app_order_resolves_custom_admin_configs(rtl_first, rtl_config):
    ordered = [rtl_config, "tests.test_checks.MyAdminConfig"]
    if not rtl_first:
        ordered.reverse()
    other_apps = [
        app
        for app in settings.INSTALLED_APPS
        if app not in {"django_rtl_admin", "django.contrib.admin"}
    ]
    with override_settings(INSTALLED_APPS=ordered + other_apps):
        warnings = checks.check_app_order(None)
    assert ids(warnings) == ([] if rtl_first else ["rtl_admin.W001"])
    if warnings:
        assert warnings[0].msg == (
            "'django_rtl_admin' is listed after 'django.contrib.admin' in INSTALLED_APPS."
        )


@override_settings(INSTALLED_APPS=["django.contrib.contenttypes", "django.contrib.auth"])
def test_the_app_order_check_is_silent_without_the_admin():
    assert checks.check_app_order(None) == []


@override_settings(RTL_ADMIN={"ENABEL_CSS": True})
def test_unknown_settings_keys_are_reported():
    warnings = checks.check_settings_keys(None)
    assert ids(warnings) == ["rtl_admin.W002"]
    assert "ENABEL_CSS" in warnings[0].msg


@override_settings(ROOT_URLCONF="tests.urls_without_i18n")
def test_a_missing_set_language_route_is_reported():
    assert "rtl_admin.W003" in ids(checks.check_language_switcher(None))


@override_settings(MIDDLEWARE=["django.contrib.sessions.middleware.SessionMiddleware"])
def test_missing_locale_middleware_is_reported():
    assert "rtl_admin.W004" in ids(checks.check_language_switcher(None))


@override_settings(
    RTL_ADMIN={"LANGUAGE_SWITCHER": False},
    ROOT_URLCONF="tests.urls_without_i18n",
    MIDDLEWARE=[],
)
def test_the_switcher_checks_are_skipped_when_it_is_disabled():
    assert checks.check_language_switcher(None) == []


@pytest.mark.parametrize(
    ("name", "value"), [(name, value) for name, choices in CHOICES.items() for value in choices]
)
def test_valid_choices_pass(name, value):
    with override_settings(RTL_ADMIN={name: value}):
        assert checks.check_settings_values(None) == []


@pytest.mark.parametrize("name", list(CHOICES))
@pytest.mark.parametrize("value", ["invalid", None, False, 1, [], {}])
def test_invalid_choices_are_errors(name, value):
    with override_settings(RTL_ADMIN={name: value}):
        errors = checks.check_settings_values(None)
    assert ids(errors) == ["rtl_admin.E001"]
    assert isinstance(errors[0], Error)
    assert errors[0].msg == (
        f"RTL_ADMIN[{name!r}] must be one of "
        f"{', '.join(repr(choice) for choice in CHOICES[name])}, got {value!r}."
    )


@override_settings(RTL_ADMIN=dict.fromkeys(CHOICES, "invalid"))
def test_all_invalid_choices_are_reported_together_by_registered_checks():
    errors = [issue for issue in run_checks() if issue.id.startswith("rtl_admin.")]
    assert ids(errors) == ["rtl_admin.E001"] * len(CHOICES)
    for name in CHOICES:
        assert any(name in error.msg for error in errors)


@pytest.mark.parametrize("value", [(), [], ("ar-eg",), ["ar-eg", "he"]])
def test_extra_rtl_language_sequences_pass(value):
    with override_settings(RTL_ADMIN={"EXTRA_RTL_LANGUAGES": value}):
        assert checks.check_settings_types(None) == []


@pytest.mark.parametrize("value", ["ar-eg", ""])
def test_a_bare_extra_rtl_language_string_is_reported(value):
    with override_settings(RTL_ADMIN={"EXTRA_RTL_LANGUAGES": value}):
        warnings = checks.check_settings_types(None)
    assert ids(warnings) == ["rtl_admin.W005"]
    assert isinstance(warnings[0], Warning)
    assert "EXTRA_RTL_LANGUAGES" in warnings[0].msg


@pytest.mark.parametrize("value", [(), [], ("ps",), ("ps-AF",), ("ar-eg",), ("he",)])
@override_settings(LANGUAGES_BIDI=["ar", "ar-dz", "he", "ps"])
def test_extra_rtl_languages_present_in_languages_bidi_pass(value):
    with override_settings(RTL_ADMIN={"EXTRA_RTL_LANGUAGES": value}):
        assert checks.check_extra_rtl_languages_bidi(None) == []


@pytest.mark.parametrize(
    ("value", "missing"),
    [
        (("tzm",), ["tzm"]),
        (("ps",), ["ps"]),
        (("tzm", "ps-AF", "ar-eg"), ["ps-AF", "tzm"]),
    ],
)
@override_settings(LANGUAGES_BIDI=["ar"])
def test_extra_rtl_languages_missing_from_languages_bidi_are_reported(value, missing):
    with override_settings(RTL_ADMIN={"EXTRA_RTL_LANGUAGES": value}):
        warnings = checks.check_extra_rtl_languages_bidi(None)
    assert ids(warnings) == ["rtl_admin.W006"]
    assert isinstance(warnings[0], Warning)
    assert warnings[0].msg == (
        "RTL_ADMIN['EXTRA_RTL_LANGUAGES'] contains language codes missing from "
        f"settings.LANGUAGES_BIDI: {', '.join(missing)}."
    )
    assert "LANGUAGES_BIDI" in warnings[0].hint


def test_a_bare_extra_rtl_language_string_skips_the_bidi_check():
    with override_settings(RTL_ADMIN={"EXTRA_RTL_LANGUAGES": "tzm"}):
        assert checks.check_extra_rtl_languages_bidi(None) == []


@pytest.mark.parametrize("value", [("AR",), ("Ar",), ("PS_AF",), ["AR-eg"]])
@override_settings(LANGUAGES_BIDI=["ar", "ps"])
def test_w006_normalizes_extra_codes_before_comparing(value):
    with override_settings(RTL_ADMIN={"EXTRA_RTL_LANGUAGES": value}):
        assert checks.check_extra_rtl_languages_bidi(None) == []


@override_settings(LANGUAGES_BIDI=["PS", "ps-AF"])
def test_w006_compares_against_the_raw_languages_bidi_entries():
    with override_settings(RTL_ADMIN={"EXTRA_RTL_LANGUAGES": ("ps",)}):
        warnings = checks.check_extra_rtl_languages_bidi(None)
    assert ids(warnings) == ["rtl_admin.W006"]
    assert "ps" in warnings[0].msg


def test_a_missing_extra_rtl_languages_setting_skips_the_bidi_check():
    assert checks.check_extra_rtl_languages_bidi(None) == []
    with override_settings(RTL_ADMIN={}):
        assert checks.check_extra_rtl_languages_bidi(None) == []


@pytest.mark.parametrize(
    "value", [None, "Arial, sans-serif", [], (), ["Arial"], ("Arial", "serif")]
)
def test_valid_font_stacks_pass(value):
    with override_settings(RTL_ADMIN={"FONT_STACK": value}):
        assert checks.check_settings_types(None) == []


@pytest.mark.parametrize("value", [True, 42, b"Arial", b"", {"Arial": "serif"}, ["Arial", 1]])
def test_invalid_font_stack_types_are_reported(value):
    with override_settings(RTL_ADMIN={"FONT_STACK": value}):
        warnings = checks.check_settings_types(None)
    assert ids(warnings) == ["rtl_admin.W005"]
    assert "FONT_STACK" in warnings[0].msg


@pytest.mark.parametrize(
    "name", [name for name, value in DEFAULTS.items() if isinstance(value, bool)]
)
@pytest.mark.parametrize("value", [True, False])
def test_boolean_switches_pass(name, value):
    with override_settings(RTL_ADMIN={name: value}):
        assert checks.check_settings_types(None) == []


@pytest.mark.parametrize(
    "name", [name for name, value in DEFAULTS.items() if isinstance(value, bool)]
)
@pytest.mark.parametrize("value", [1, 0, "False", None, []])
def test_non_boolean_switches_are_reported(name, value):
    with override_settings(RTL_ADMIN={name: value}):
        warnings = checks.check_settings_types(None)
    assert ids(warnings) == ["rtl_admin.W005"]
    assert name in warnings[0].msg


@pytest.mark.parametrize(
    "value", [None, {}, DEFAULTS, MappingProxyType({}), MappingProxyType(DEFAULTS)]
)
def test_settings_mappings_and_none_pass(value):
    with override_settings(RTL_ADMIN=value):
        assert checks.check_settings_keys(None) == []
        assert checks.check_settings_values(None) == []
        assert checks.check_settings_types(None) == []
        assert checks.check_language_switcher(None) == []


@pytest.mark.parametrize("value", [None, MappingProxyType({})])
def test_none_and_empty_mappings_keep_language_switcher_checks_running(value):
    with override_settings(
        RTL_ADMIN=value,
        ROOT_URLCONF="tests.urls_without_i18n",
        MIDDLEWARE=[],
    ):
        issues = [issue for issue in run_checks() if issue.id.startswith("rtl_admin.")]
    assert ids(issues) == ["rtl_admin.W003", "rtl_admin.W004"]


@override_settings(
    RTL_ADMIN=MappingProxyType({"NUMERALS": "invalid", "ENABEL_CSS": True}),
    ROOT_URLCONF="tests.urls_without_i18n",
    MIDDLEWARE=[],
)
def test_mappings_keep_choice_key_and_language_switcher_checks_running():
    issues = [issue for issue in run_checks() if issue.id.startswith("rtl_admin.")]
    assert ids(issues) == ["rtl_admin.E001", "rtl_admin.W002", "rtl_admin.W003", "rtl_admin.W004"]
    assert any("NUMERALS" in issue.msg for issue in issues if issue.id == "rtl_admin.E001")
    assert any("ENABEL_CSS" in issue.msg for issue in issues if issue.id == "rtl_admin.W002")


@override_settings(
    RTL_ADMIN=MappingProxyType({"LANGUAGE_SWITCHER": False}),
    ROOT_URLCONF="tests.urls_without_i18n",
    MIDDLEWARE=[],
)
def test_mappings_can_disable_the_language_switcher_checks():
    assert checks.check_language_switcher(None) == []
    assert checks.check_settings_types(None) == []


@override_settings(RTL_ADMIN=MappingProxyType({"FONT_STACK": 42}))
def test_mapping_options_are_still_type_checked():
    warnings = checks.check_settings_types(None)
    assert ids(warnings) == ["rtl_admin.W005"]
    assert "FONT_STACK" in warnings[0].msg


@pytest.mark.parametrize("value", ["invalid", "", [], ["FONT_STACK"], (), True, 0, 1])
def test_non_mapping_settings_are_reported_without_crashing_other_checks(value):
    with override_settings(RTL_ADMIN=value):
        issues = [issue for issue in run_checks() if issue.id.startswith("rtl_admin.")]
    assert ids(issues) == ["rtl_admin.W005"]
    assert issues[0].msg == "RTL_ADMIN must be a mapping or None."


@override_settings(
    RTL_ADMIN={
        "EXTRA_RTL_LANGUAGES": "ar-eg",
        "FONT_STACK": 42,
        "LANGUAGE_SWITCHER": "False",
        "ENABLE_CSS": 0,
    }
)
def test_all_invalid_types_are_reported_together():
    warnings = checks.check_settings_types(None)
    assert ids(warnings) == ["rtl_admin.W005"] * 4


def test_the_checks_are_registered_with_django():
    from django.core.checks import registry

    registered = {check.__name__ for check in registry.registry.get_checks()}
    assert {
        "check_app_order",
        "check_settings_keys",
        "check_settings_values",
        "check_settings_types",
        "check_language_switcher",
    } <= registered
