"""Fixtures for the Playwright browser tests.

The tests drive a real Chromium against pytest-django's live server, so they
need Playwright and its browser:

    python -m pip install playwright
    python -m playwright install chromium

or simply ``nox -s e2e``.  Without Playwright the whole directory is skipped;
set ``RTL_ADMIN_E2E=1`` to turn a missing browser into a failure instead of a
skip, as the CI job does.
"""

from __future__ import annotations

import datetime
import os
import re
import threading
from decimal import Decimal
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = Path(
    os.environ.get("RTL_ADMIN_E2E_ARTIFACTS", REPO_ROOT / "test-artifacts" / "e2e")
)
WIDTHS = (360, 1280)
VIEWPORT_HEIGHT = 900
PASSWORD = "e2e-password"


@pytest.fixture(scope="session")
def allow_async_unsafe():
    """Let the ORM run while Playwright's event loop is alive.

    Playwright's sync API runs an event loop in the test thread, which trips
    Django's async-safety guard on every ORM call made while the browser is
    open.  The guard is lifted only for as long as the browser runs, so a
    session without browser tests keeps it.
    """
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("DJANGO_ALLOW_ASYNC_UNSAFE", "true")
        yield


@pytest.fixture(scope="session")
def browser(allow_async_unsafe):
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except sync_api.Error as exc:
            if os.environ.get("RTL_ADMIN_E2E"):
                raise
            pytest.skip(f"Chromium is not installed (python -m playwright install chromium): {exc}")
        yield browser
        browser.close()


class SerialApp:
    """WSGI wrapper that lets the live server handle one request at a time.

    The test database is in-memory SQLite, so the live server's request
    threads all share the test's single connection.  Two requests using it at
    once corrupt each other's results (an ``IndexError`` deep in the ORM and a
    500 page), which made the suite flaky.  The lock also lets the test keep
    the server quiet while it writes to the database itself.
    """

    def __init__(self, app):
        self.app = app
        self.lock = threading.RLock()
        self._idle = threading.Condition()
        self._active = 0

    def __call__(self, environ, start_response):
        with self._idle:
            self._active += 1
        try:
            with self.lock:
                response = self.app(environ, start_response)
                try:
                    return list(response)
                finally:
                    if hasattr(response, "close"):
                        response.close()
        finally:
            with self._idle:
                self._active -= 1
                self._idle.notify_all()

    def wait_until_idle(self, timeout=30):
        with self._idle:
            if not self._idle.wait_for(lambda: self._active == 0, timeout):
                raise RuntimeError(f"live server still busy after {timeout}s")


@pytest.fixture(scope="session")
def live_server_app(live_server):
    httpd = live_server.thread.httpd
    app = SerialApp(httpd.get_app())
    httpd.set_app(app)
    return app


@pytest.fixture(scope="session")
def artifacts_dir():
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    return ARTIFACTS_DIR


@pytest.fixture
def e2e_data(transactional_db):
    from django.contrib.auth import get_user_model

    from tests.testapp.models import Book, Category, Chapter, Review

    user = get_user_model().objects.create_superuser("admin", "admin@example.com", PASSWORD)
    fiction = Category.objects.create(name="Fiction")
    history = Category.objects.create(name="تاريخ")
    Category.objects.create(name="Science")

    titles = [
        ("مقدمة ابن خلدون", "978-9953-0-0001-1", history, "published"),
        ("Pride and Prejudice", "978-0-14-143951-8", fiction, "published"),
        ("ألف ليلة وليلة", "978-9953-0-0002-8", fiction, "draft"),
        ("A Brief History of Time", "978-0-553-38016-3", None, "published"),
        ("رجال في الشمس", "978-9953-0-0003-5", fiction, "draft"),
        ("The Cairo Trilogy: Palace Walk", "978-0-385-26466-4", fiction, "published"),
        ("موسم الهجرة إلى الشمال", "978-9953-0-0004-2", fiction, "published"),
        ("Guns, Germs, and Steel", "978-0-393-31755-8", history, "draft"),
        ("الأيام", "978-9953-0-0005-9", None, "published"),
        ("Dune", "978-0-441-01359-3", fiction, "published"),
        ("تاريخ الطبري، المجلد الأول", "978-9953-0-0006-6", history, "draft"),
        ("Sapiens", "978-0-06-231609-7", history, "published"),
    ]
    books = []
    for index, (title, isbn, category, status) in enumerate(titles):
        books.append(
            Book.objects.create(
                title=title,
                isbn=isbn,
                category=category,
                status=status,
                published_on=datetime.date(2024 + index % 3, 1 + index, 10),
                available_from=datetime.datetime(2025, 1, 1, 9, 30, tzinfo=datetime.timezone.utc),
                launch_time=datetime.time(18, 45),
                price=Decimal("120.50") + index,
                summary="سيرة ذاتية — an autobiography first published in 1929.",
            )
        )
    book = books[0]
    for number, title in enumerate(["الفصل الأول", "Chapter two: v1.2.3"], start=1):
        Chapter.objects.create(book=book, number=number, title=title)
    Review.objects.create(
        book=book,
        reviewer="Layla",
        body="كتاب رائع — a classic of historiography.",
        reviewed_at=datetime.datetime(2025, 3, 1, 12, 0, tzinfo=datetime.timezone.utc),
    )
    return {"user": user, "book": book, "books": books}


@pytest.fixture
def open_admin(browser, live_server, live_server_app, e2e_data, request, artifacts_dir):
    """Open an admin URL in a fresh browser context.

    ``open_admin(path, lang="ar", scheme="dark", width=360, login=True)``
    returns a Playwright page with the language cookie set and, unless
    ``login=False``, an authenticated superuser session.
    """
    from django.conf import settings
    from django.test import Client

    contexts = []

    def _open(path, *, lang, scheme="light", width=1280, login=True):
        context = browser.new_context(
            viewport={"width": width, "height": VIEWPORT_HEIGHT},
            color_scheme=scheme,
            locale="ar-EG" if lang == "ar" else "en-US",
            base_url=live_server.url,
        )
        contexts.append(context)
        cookies = [{"name": settings.LANGUAGE_COOKIE_NAME, "value": lang, "url": live_server.url}]
        if login:
            client = Client()
            with live_server_app.lock:
                client.force_login(e2e_data["user"])
            session_cookie = client.cookies[settings.SESSION_COOKIE_NAME].value
            cookies.append(
                {
                    "name": settings.SESSION_COOKIE_NAME,
                    "value": session_cookie,
                    "url": live_server.url,
                }
            )
        context.add_cookies(cookies)
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.js_errors = errors
        page.goto(path)
        page.wait_for_load_state("load")
        return page

    yield _open
    for context in contexts:
        context.close()
    # Requests still in flight would race the database flush that follows.
    live_server_app.wait_until_idle()


@pytest.fixture
def snapshot(artifacts_dir, request):
    """Save a full-page screenshot under test-artifacts/e2e/."""
    test_name = re.sub(r"[^\w.-]+", "_", request.node.name).strip("_")

    def _snapshot(page, label):
        width = page.viewport_size["width"]
        name = re.sub(r"[^\w.-]+", "_", f"{test_name}-{label}-{width}px")
        path = artifacts_dir / f"{name}.png"
        page.screenshot(path=str(path), full_page=True, animations="disabled")
        return path

    return _snapshot
