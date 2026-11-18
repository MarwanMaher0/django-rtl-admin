"""The ``RTL_ADMIN`` settings namespace."""

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from django_rtl_admin.conf import DEFAULTS, RTLAdminSettings, rtl_settings


def test_every_default_is_readable():
    assert DEFAULTS["ISOLATE_READONLY_FIELDS"] is True
    for key, value in DEFAULTS.items():
        assert getattr(rtl_settings, key) == value


def test_unknown_attributes_raise():
    with pytest.raises(AttributeError, match="Invalid RTL_ADMIN setting"):
        rtl_settings.NOT_A_SETTING


@override_settings(RTL_ADMIN={"ENABLE_CSS": False, "CURRENCY": "EGP"})
def test_project_settings_override_the_defaults():
    assert rtl_settings.ENABLE_CSS is False
    assert rtl_settings.CURRENCY == "EGP"
    # untouched keys keep their default
    assert rtl_settings.LANGUAGE_SWITCHER is True


def test_settings_are_reread_after_an_override_is_undone():
    with override_settings(RTL_ADMIN={"CURRENCY": "EGP"}):
        assert rtl_settings.CURRENCY == "EGP"
    assert rtl_settings.CURRENCY == DEFAULTS["CURRENCY"]


@override_settings(RTL_ADMIN={"ISOLATION_DIRECTION": "diagonal"})
def test_a_bad_choice_is_reported():
    with pytest.raises(ImproperlyConfigured, match="ISOLATION_DIRECTION"):
        rtl_settings.ISOLATION_DIRECTION


@override_settings(RTL_ADMIN={"NUMERALS": "roman"})
def test_a_bad_numbering_system_is_reported():
    with pytest.raises(ImproperlyConfigured, match="NUMERALS"):
        rtl_settings.NUMERALS


@override_settings(RTL_ADMIN={"ENABEL_CSS": True, "TYPO": 1})
def test_unknown_keys_are_listed():
    assert rtl_settings.unknown_keys() == ["ENABEL_CSS", "TYPO"]


def test_no_unknown_keys_by_default():
    assert rtl_settings.unknown_keys() == []


@override_settings(RTL_ADMIN={"CURRENCY": "GBP"})
def test_item_access_matches_attribute_access():
    assert rtl_settings["CURRENCY"] == rtl_settings.CURRENCY == "GBP"


def test_a_standalone_instance_uses_its_own_defaults():
    custom = RTLAdminSettings({"ENABLE_CSS": False})
    assert custom.ENABLE_CSS is False
