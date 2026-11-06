"""Tests for the deployable example demo project and reset_demo command."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ImproperlyConfigured

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_DIR = REPO_ROOT / "example"


def _load_example_settings(env_overrides: dict[str, str | None]):
    spec = importlib.util.spec_from_file_location(
        "example_config_settings_test",
        EXAMPLE_DIR / "config" / "settings.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    cleaned_env = {
        k: v
        for k, v in os.environ.items()
        if k
        not in {
            "SECRET_KEY",
            "DJANGO_SECRET_KEY",
            "DJANGO_ENV",
            "DEBUG",
            "DJANGO_DEBUG",
            "ALLOWED_HOSTS",
            "DJANGO_ALLOWED_HOSTS",
            "CSRF_TRUSTED_ORIGINS",
            "DJANGO_CSRF_TRUSTED_ORIGINS",
            "DATABASE_URL",
            "PORT",
            "WEB_CONCURRENCY",
            "RENDER",
            "FLY_APP_NAME",
            "FLY_MACHINE_ID",
            "DYNO",
            "K_SERVICE",
        }
    }
    for key, value in env_overrides.items():
        if value is not None:
            cleaned_env[key] = value
    with mock.patch.dict(os.environ, cleaned_env, clear=True):
        spec.loader.exec_module(module)
    return module


def test_example_settings_defaults_are_production_safe_and_work_locally_with_no_env_vars():
    # manage.py sets DJANGO_ENV="development" by default when invoked locally.
    settings_mod = _load_example_settings({"DJANGO_ENV": "development"})
    assert settings_mod.DEBUG is False
    assert settings_mod.LOCAL_DEV is True
    assert settings_mod.SECRET_KEY == settings_mod._LOCAL_DEV_SECRET_KEY
    assert "localhost" in settings_mod.ALLOWED_HOSTS
    assert "127.0.0.1" in settings_mod.ALLOWED_HOSTS
    assert settings_mod.CSRF_TRUSTED_ORIGINS == []
    assert settings_mod.DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3"
    assert settings_mod.DATABASES["default"]["NAME"] == EXAMPLE_DIR / "db.sqlite3"
    assert (
        settings_mod.MIDDLEWARE[0]
        == "django.middleware.security.SecurityMiddleware"
    )
    if importlib.util.find_spec("whitenoise") is not None:
        assert (
            settings_mod.MIDDLEWARE[1]
            == "whitenoise.middleware.WhiteNoiseMiddleware"
        )
        assert (
            settings_mod.STORAGES["staticfiles"]["BACKEND"]
            == "whitenoise.storage.CompressedStaticFilesStorage"
        )
    else:
        assert (
            "whitenoise.middleware.WhiteNoiseMiddleware"
            not in settings_mod.MIDDLEWARE
        )
        assert (
            settings_mod.STORAGES["staticfiles"]["BACKEND"]
            == "django.contrib.staticfiles.storage.StaticFilesStorage"
        )


def test_example_settings_fails_at_startup_when_debug_off_and_secret_key_missing_or_insecure():
    # Without manage.py's DJANGO_ENV="development" (e.g. any WSGI/ASGI server or
    # generic get_wsgi_application()/get_asgi_application() with no env vars),
    # LOCAL_DEV is False and settings.py refuses to start without SECRET_KEY.
    with pytest.raises(ImproperlyConfigured, match="SECRET_KEY"):
        _load_example_settings({})

    with pytest.raises(ImproperlyConfigured, match="SECRET_KEY"):
        _load_example_settings({"DJANGO_ENV": "production"})

    with pytest.raises(ImproperlyConfigured, match="SECRET_KEY"):
        _load_example_settings({"DEBUG": "1", "DJANGO_ENV": "production"})

    with pytest.raises(ImproperlyConfigured, match="SECRET_KEY"):
        _load_example_settings({"DEBUG": "1"})

    with pytest.raises(ImproperlyConfigured, match="SECRET_KEY"):
        _load_example_settings(
            {"DEBUG": "1", "DJANGO_ENV": "development", "RENDER": "true"}
        )

    with pytest.raises(ImproperlyConfigured, match="SECRET_KEY"):
        _load_example_settings(
            {"DEBUG": "1", "DJANGO_ENV": "development", "FLY_APP_NAME": "demo-app"}
        )

    with pytest.raises(ImproperlyConfigured, match="SECRET_KEY"):
        _load_example_settings(
            {"DEBUG": "1", "DJANGO_ENV": "development", "PORT": "8000"}
        )

    with pytest.raises(ImproperlyConfigured, match="SECRET_KEY"):
        _load_example_settings(
            {
                "DEBUG": "1",
                "DJANGO_ENV": "production",
                "SECRET_KEY": "django-insecure-cannot-use-in-prod",
            }
        )

    with pytest.raises(ImproperlyConfigured, match="SECRET_KEY"):
        _load_example_settings({"DEBUG": "false"})

    with pytest.raises(ImproperlyConfigured, match="SECRET_KEY"):
        _load_example_settings({"DEBUG": "0", "SECRET_KEY": ""})

    with pytest.raises(ImproperlyConfigured, match="SECRET_KEY"):
        _load_example_settings({"PORT": "8000"})

    with pytest.raises(ImproperlyConfigured, match="SECRET_KEY"):
        _load_example_settings({"DJANGO_ENV": "development", "PORT": "8000"})

    with pytest.raises(ImproperlyConfigured, match="SECRET_KEY"):
        _load_example_settings(
            {"DEBUG": "false", "SECRET_KEY": "django-insecure-cannot-use-in-prod"}
        )

    # Every non-manage.py entry point (config.wsgi, generic get_wsgi_application(),
    # generic get_asgi_application()) must fail at settings import time without SECRET_KEY.
    clean_server_env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "PYTHONPATH": os.pathsep.join([str(EXAMPLE_DIR), str(REPO_ROOT / "src")]),
        "DJANGO_SETTINGS_MODULE": "config.settings",
    }
    for entrypoint_stmt in (
        "import config.wsgi",
        "from django.core.wsgi import get_wsgi_application; get_wsgi_application()",
        "from django.core.asgi import get_asgi_application; get_asgi_application()",
    ):
        res = subprocess.run(
            [sys.executable, "-c", entrypoint_stmt],
            cwd=str(EXAMPLE_DIR),
            env=clean_server_env,
            capture_output=True,
            text=True,
        )
        assert res.returncode != 0
        assert "ImproperlyConfigured" in res.stderr
        assert "SECRET_KEY" in res.stderr

    settings_mod = _load_example_settings(
        {"DEBUG": "false", "SECRET_KEY": "strong-production-secret-key"}
    )
    assert settings_mod.DEBUG is False
    assert settings_mod.LOCAL_DEV is False
    assert settings_mod.SECRET_KEY == "strong-production-secret-key"
    assert settings_mod.USING_LOCAL_DEV_SECRET_KEY is False

    debug_prod_mod = _load_example_settings(
        {
            "DEBUG": "1",
            "DJANGO_ENV": "production",
            "SECRET_KEY": "strong-production-secret-key",
        }
    )
    assert debug_prod_mod.DEBUG is True
    assert debug_prod_mod.LOCAL_DEV is False


def test_example_settings_reads_environment_variables():
    settings_mod = _load_example_settings(
        {
            "SECRET_KEY": "prod-secret-value",
            "DEBUG": "false",
            "ALLOWED_HOSTS": "demo.example.com, .fly.dev ",
            "CSRF_TRUSTED_ORIGINS": "https://demo.example.com, https://*.fly.dev",
            "DATABASE_URL": "postgres://dbuser:dbpass@db.internal:5432/demodb",
        }
    )
    assert settings_mod.SECRET_KEY == "prod-secret-value"
    assert settings_mod.DEBUG is False
    assert settings_mod.ALLOWED_HOSTS == ["demo.example.com", ".fly.dev"]
    assert settings_mod.CSRF_TRUSTED_ORIGINS == [
        "https://demo.example.com",
        "https://*.fly.dev",
    ]
    db = settings_mod.DATABASES["default"]
    assert db["ENGINE"] == "django.db.backends.postgresql"
    assert db["NAME"] == "demodb"
    assert db["USER"] == "dbuser"
    assert db["PASSWORD"] == "dbpass"
    assert db["HOST"] == "db.internal"
    assert str(db["PORT"]) == "5432"


@pytest.mark.django_db
def test_configure_readonly_demo_user_limits_view_permissions_to_demo_models():
    from tests.testapp.models import Thing

    if str(EXAMPLE_DIR) not in sys.path:
        sys.path.insert(0, str(EXAMPLE_DIR))
    from library.management.commands.reset_demo import configure_readonly_demo_user

    User = get_user_model()
    # Start as a superuser to verify it is downgraded to a view-only staff user.
    User.objects.create_superuser("demo", "demo@example.com", "oldpass")

    user, group = configure_readonly_demo_user(
        username="demo",
        password="demo12345",
        email="demo@example.com",
        models=(Thing,),
    )
    user.refresh_from_db()
    assert user.is_active is True
    assert user.is_staff is True
    assert user.is_superuser is False
    assert user.check_password("demo12345")
    assert list(user.groups.all()) == [group]
    assert Group.objects.filter(pk=group.pk).exists()

    perms = {
        f"{p.content_type.app_label}.{p.codename}"
        for p in group.permissions.select_related("content_type")
    }
    assert perms == {"testapp.view_thing"}
    assert not user.has_perm("auth.view_user")
    assert not user.has_perm("auth.view_group")
    assert not user.has_perm("auth.change_user")
    assert not user.has_perm("auth.change_group")
    assert not user.has_perm("testapp.add_thing")
    assert not user.has_perm("testapp.change_thing")
    assert not user.has_perm("testapp.delete_thing")
    assert user.has_perm("testapp.view_thing")


def test_reset_demo_command_and_admin_endpoints_end_to_end(tmp_path):
    db_path = tmp_path / "demo.sqlite3"
    static_root = tmp_path / "staticfiles"
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.settings",
        "DATABASE_URL": f"sqlite:////{db_path}",
        "STATIC_ROOT": str(static_root),
        "DEBUG": "false",
        "SECRET_KEY": "test-production-secret-key",
    }
    res = subprocess.run(
        [sys.executable, str(EXAMPLE_DIR / "manage.py"), "reset_demo"],
        cwd=str(EXAMPLE_DIR),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "2 publishers, 5 books, 10 chapters." in res.stdout
    assert "Configured read-only staff user 'demo'" in res.stdout

    # Verify HTTP responses, language switching, auth model restrictions, and password_change block.
    probe = (
        "import importlib.util\n"
        "import django\n"
        "django.setup()\n"
        "from django.conf import settings\n"
        "from django.contrib.staticfiles.views import serve as serve_static\n"
        "from django.test import Client\n"
        "from django.contrib.auth import get_user_model\n"
        "from django.contrib.auth.models import Group\n"
        "import config.urls\n"
        "from library.models import Book, Chapter\n"
        "assert settings.LOCAL_DEV is False\n"
        "# Outside local development, Django's insecure static view must never be mounted.\n"
        "assert not any(getattr(p, 'callback', None) is serve_static for p in config.urls.urlpatterns)\n"
        "assert Book.objects.count() == 5\n"
        "assert Chapter.objects.count() == 10\n"
        "User = get_user_model()\n"
        "demo = User.objects.get(username='demo')\n"
        "assert demo.is_staff and not demo.is_superuser\n"
        "group = Group.objects.get(name='Demo Read-Only')\n"
        "perms = {f'{p.content_type.app_label}.{p.codename}' for p in group.permissions.select_related('content_type')}\n"
        "assert perms == {'library.view_publisher', 'library.view_book', 'library.view_chapter'}\n"
        "assert demo.has_perm('library.view_book')\n"
        "assert not demo.has_perm('library.add_book')\n"
        "assert not demo.has_perm('library.change_book')\n"
        "assert not demo.has_perm('library.delete_book')\n"
        "assert not demo.has_perm('auth.view_user')\n"
        "assert not demo.has_perm('auth.view_group')\n"
        "client = Client(HTTP_HOST='localhost')\n"
        "assert client.get('/healthz/').status_code == 200\n"
        "login_resp = client.get('/admin/login/')\n"
        "assert login_resp.status_code == 200\n"
        "assert client.login(username='demo', password='demo12345')\n"
        "switch_resp = client.post('/i18n/setlang/', {'language': 'ar', 'next': '/admin/library/book/'})\n"
        "assert switch_resp.status_code == 302\n"
        "changelist = client.get('/admin/library/book/')\n"
        "assert changelist.status_code == 200\n"
        "html = changelist.content.decode('utf-8')\n"
        "assert 'dir=\"rtl\"' in html\n"
        "assert 'مقدمة ابن خلدون' in html\n"
        "assert '/admin/password_change/' not in html\n"
        "if importlib.util.find_spec('whitenoise') is not None:\n"
        "    assert client.get('/static/admin/css/base.css').status_code == 200\n"
        "    assert client.get('/static/django_rtl_admin/css/rtl-admin.css').status_code == 200\n"
        "else:\n"
        "    assert client.get('/static/django_rtl_admin/css/rtl-admin.css').status_code == 404\n"
        "assert client.get('/admin/library/book/add/').status_code == 403\n"
        "assert client.get('/admin/auth/user/').status_code == 403\n"
        "assert client.get('/admin/auth/group/').status_code == 403\n"
        "assert client.get('/admin/password_change/').status_code == 403\n"
        "assert client.post('/admin/password_change/', {\n"
        "    'old_password': 'demo12345',\n"
        "    'new_password1': 'HackedPass999!',\n"
        "    'new_password2': 'HackedPass999!',\n"
        "}).status_code == 403\n"
        "assert client.get('/admin/password_change/done/').status_code == 403\n"
        "demo.refresh_from_db()\n"
        "assert demo.check_password('demo12345')\n"
        "# Other staff users (non-demo, non-superuser) MUST still see the link and be able to change their own password.\n"
        "other_staff = User.objects.create_user(\n"
        "    username='editor_staff',\n"
        "    email='editor@example.com',\n"
        "    password='InitialStaffPass123!',\n"
        "    is_staff=True,\n"
        "    is_superuser=False,\n"
        ")\n"
        "staff_client = Client(HTTP_HOST='localhost')\n"
        "assert staff_client.login(username='editor_staff', password='InitialStaffPass123!')\n"
        "staff_index = staff_client.get('/admin/')\n"
        "assert staff_index.status_code == 200\n"
        "assert '/admin/password_change/' in staff_index.content.decode('utf-8')\n"
        "assert staff_client.get('/admin/password_change/').status_code == 200\n"
        "change_resp = staff_client.post('/admin/password_change/', {\n"
        "    'old_password': 'InitialStaffPass123!',\n"
        "    'new_password1': 'UpdatedStaffPass456!',\n"
        "    'new_password2': 'UpdatedStaffPass456!',\n"
        "})\n"
        "assert change_resp.status_code == 302\n"
        "assert staff_client.get('/admin/password_change/done/').status_code == 200\n"
        "other_staff.refresh_from_db()\n"
        "assert other_staff.check_password('UpdatedStaffPass456!')\n"
    )
    subprocess.run(
        [sys.executable, "-c", probe],
        cwd=str(EXAMPLE_DIR),
        env=env,
        check=True,
    )

    # In local development (LOCAL_DEV=True via manage.py / DJANGO_ENV="development"
    # with no production env vars), static files are served even without WhiteNoise.
    local_dev_env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "PYTHONPATH": os.pathsep.join([str(EXAMPLE_DIR), str(REPO_ROOT / "src")]),
        "DJANGO_SETTINGS_MODULE": "config.settings",
        "DJANGO_ENV": "development",
    }
    local_dev_probe = (
        "import django\n"
        "django.setup()\n"
        "from django.conf import settings\n"
        "from django.test import Client\n"
        "assert settings.LOCAL_DEV is True\n"
        "client = Client(HTTP_HOST='localhost')\n"
        "assert client.get('/static/admin/css/base.css').status_code == 200\n"
        "assert client.get('/static/django_rtl_admin/css/rtl-admin.css').status_code == 200\n"
    )
    subprocess.run(
        [sys.executable, "-c", local_dev_probe],
        cwd=str(EXAMPLE_DIR),
        env=local_dev_env,
        check=True,
    )


def test_deployment_artifacts_and_shared_reset_schedule():
    assert (REPO_ROOT / "Dockerfile").is_file()
    assert (REPO_ROOT / ".dockerignore").is_file()
    assert (REPO_ROOT / "fly.toml").is_file()
    assert (REPO_ROOT / "render.yaml").is_file()
    assert (EXAMPLE_DIR / "Dockerfile").is_file()
    assert (EXAMPLE_DIR / "README.md").is_file()
    assert (REPO_ROOT / "docs" / "deployment.md").is_file()

    requirements = (EXAMPLE_DIR / "requirements.txt").read_text(encoding="utf-8")
    assert "psycopg[binary]" in requirements

    render_yaml = (REPO_ROOT / "render.yaml").read_text(encoding="utf-8")
    assert "databases:" in render_yaml
    assert "name: django-rtl-admin-demo-db" in render_yaml
    assert 'schedule: "0 * * * *"' in render_yaml
    assert "plan: starter" in render_yaml
    assert render_yaml.count("fromDatabase:") == 2
    assert "RESET_DEMO_INTERVAL_SECONDS" not in render_yaml

    fly_toml = (REPO_ROOT / "fly.toml").read_text(encoding="utf-8")
    assert 'RESET_DEMO_ON_STARTUP = "1"' in fly_toml
    assert 'RESET_DEMO_INTERVAL_SECONDS = "3600"' in fly_toml

    entrypoint = (EXAMPLE_DIR / "entrypoint.sh").read_text(encoding="utf-8")
    assert "RESET_DEMO_INTERVAL_SECONDS" in entrypoint
