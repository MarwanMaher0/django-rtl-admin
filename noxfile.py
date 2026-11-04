"""Test every supported Python/Django combination.

    nox -l                          list the cells
    nox                             run them all, then ruff
    nox -s "tests(py3.12-django5.2)"
    nox -s "tests(py3.12-django5.2)" -- -k bidi

Each test cell installs the package, pytest and one Django series, runs the
suite under coverage and prints the report. With uv on PATH, missing Python
interpreters are downloaded automatically.
"""

from __future__ import annotations

import os

import nox

nox.needs_version = ">=2024.3.2"
nox.options.default_venv_backend = "uv|virtualenv"
nox.options.sessions = ["tests", "lint"]

PYTHONS = ["3.10", "3.11", "3.12", "3.13", "3.14"]
DJANGOS = ["4.2", "5.0", "5.1", "5.2", "6.0", "6.1"]

# Django's official support matrix:
# https://docs.djangoproject.com/en/dev/faq/install/#what-python-version-can-i-use-with-django
DJANGO_PYTHONS = {
    "4.2": ("3.8", "3.9", "3.10", "3.11", "3.12"),
    "5.0": ("3.10", "3.11", "3.12"),
    "5.1": ("3.10", "3.11", "3.12", "3.13"),
    "5.2": ("3.10", "3.11", "3.12", "3.13", "3.14"),
    "6.0": ("3.12", "3.13", "3.14"),
    "6.1": ("3.12", "3.13", "3.14"),
}

# The one cell that also runs without Babel, to exercise the fallback path.
NO_BABEL_CELL = ("3.12", "5.2")


def _cells() -> list[nox.param]:
    cells = []
    for django in DJANGOS:
        for python in PYTHONS:
            if python not in DJANGO_PYTHONS[django]:
                continue
            cells.append(nox.param(python, django, True, id=f"py{python}-django{django}"))
            if (python, django) == NO_BABEL_CELL:
                cells.append(
                    nox.param(python, django, False, id=f"py{python}-django{django}-nobabel")
                )
    return cells


@nox.session
@nox.parametrize("python,django,babel", _cells())
def tests(session: nox.Session, django: str, babel: bool) -> None:
    """Run the test suite under coverage for one Python/Django cell."""
    requirements = [
        "-e",
        ".",
        f"Django~={django}.0",
        "pytest>=8",
        "pytest-django>=4.8",
        "coverage[toml]>=7.5",
    ]
    if babel:
        requirements.append("Babel>=2.12")
    session.install(*requirements)

    session.run(
        "python",
        "-c",
        "import importlib.util, sys, django\n"
        "print(sys.version)\n"
        "print('Django', django.get_version())\n"
        "has_babel = importlib.util.find_spec('babel') is not None\n"
        "print('Babel', __import__('babel').__version__ if has_babel else 'not installed')\n"
        f"assert has_babel is {babel}, 'Babel should {'' if babel else 'not '}be installed'",
    )

    session.run("coverage", "run", "-m", "pytest", *session.posargs)
    session.run("coverage", "report")
    session.run("coverage", "xml")
    session.run("coverage", "lcov")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        table = session.run("coverage", "report", "--format=markdown", silent=True)
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(f"### Coverage: `{session.name}`\n\n{table}\n")


@nox.session
def lint(session: nox.Session) -> None:
    """ruff, with the rules in pyproject.toml."""
    session.install("ruff")
    session.run("ruff", "check", ".")
