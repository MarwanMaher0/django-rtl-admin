"""The package ships what it claims to ship."""

import importlib.util
import pathlib
import re
import subprocess
import sys

import pytest

import django_rtl_admin

ROOT = pathlib.Path(django_rtl_admin.__file__).parent
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKFLOWS = REPO_ROOT / ".github" / "workflows"


def _workflows():
    if not WORKFLOWS.is_dir():
        pytest.skip("workflow files are only present in a repository checkout")
    yaml = pytest.importorskip("yaml")
    return {
        path.name: yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in sorted(WORKFLOWS.glob("*.yml"))
    }


def _triggers(workflow):
    return workflow["on"] if "on" in workflow else workflow[True]


def _needs(job):
    needs = job.get("needs", [])
    return [needs] if isinstance(needs, str) else list(needs)


def _depends_on(jobs, name, target):
    pending, seen = _needs(jobs[name]), set()
    while pending:
        current = pending.pop()
        if current == target:
            return True
        if current not in seen:
            seen.add(current)
            pending.extend(_needs(jobs[current]))
    return False


def test_the_stylesheet_is_part_of_the_package():
    assert (ROOT / "static" / "django_rtl_admin" / "css" / "rtl-admin.css").is_file()


def test_the_switcher_script_is_part_of_the_package():
    assert (ROOT / "static" / "django_rtl_admin" / "js" / "language_switcher.js").is_file()


def test_the_slug_script_is_part_of_the_package():
    assert (ROOT / "static" / "django_rtl_admin" / "js" / "slug.js").is_file()


def test_the_templates_are_part_of_the_package():
    assert (ROOT / "templates" / "admin" / "base_site.html").is_file()
    assert (ROOT / "templates" / "django_rtl_admin" / "base_site.html").is_file()
    assert (ROOT / "templates" / "django_rtl_admin" / "language_switcher.html").is_file()


def test_compiled_translations_are_part_of_the_package():
    for code in ("ar", "ckb", "fa", "he", "ug", "ur"):
        assert (ROOT / "locale" / code / "LC_MESSAGES" / "django.mo").is_file()


def test_the_type_marker_is_part_of_the_package():
    # PEP 561: without it type checkers ignore the package's annotations.
    assert (ROOT / "py.typed").is_file()


def test_the_public_api_is_importable():
    for name in django_rtl_admin.__all__:
        assert getattr(django_rtl_admin, name) is not None


def test_package_version_matches_pyproject_toml():
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    project_section = re.search(r"(?ms)^\[project\]\s*\n(.*?)(?=^\[|\Z)", pyproject)
    assert project_section is not None
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"\s*$', project_section.group(1))
    assert match is not None
    assert django_rtl_admin.__version__ == match.group(1)


def test_the_stylesheet_prefers_logical_properties():
    css = (ROOT / "static" / "django_rtl_admin" / "css" / "rtl-admin.css").read_text()
    logical = css.count("-inline-start") + css.count("-inline-end") + css.count("inset-inline")
    assert logical > 60


def test_the_sdist_includes_governance_and_nox_files():
    for name in ("noxfile.py", "CONTRIBUTING.md", "SECURITY.md"):
        assert (REPO_ROOT / name).is_file()
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for entry in ('"/noxfile.py"', '"/CONTRIBUTING.md"', '"/SECURITY.md"'):
        assert entry in pyproject
    assert re.search(r"(?m)^fail_under\s*=\s*95\s*$", pyproject)


def test_github_workflows_pin_actions_by_full_sha():
    workflows_dir = REPO_ROOT / ".github" / "workflows"
    if not workflows_dir.is_dir():
        pytest.skip("workflow files are only present in a repository checkout")
    pinned = re.compile(
        r"^(?:[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}\s+#\s*v\d+"
        r"|\./\.github/workflows/[\w.-]+\.yml$)"
    )
    for workflow in sorted(workflows_dir.glob("*.yml")):
        text = workflow.read_text(encoding="utf-8")
        uses = re.findall(r"^\s*(?:-\s*)?uses:\s*(.+?)\s*$", text, flags=re.MULTILINE)
        assert uses, f"no uses: steps found in {workflow.name}"
        for ref in uses:
            assert pinned.match(ref), f"unpinned action in {workflow.name}: {ref}"
    ci_text = (workflows_dir / "ci.yml").read_text(encoding="utf-8")
    assert "\n  sdist:\n" in ci_text
    assert 'pytest -m "not e2e"' in ci_text
    assert (workflows_dir / "docs.yml").is_file()
    assert not (REPO_ROOT / ".readthedocs.yaml").exists()


def test_dependabot_tracks_github_actions_and_pip_weekly_in_groups():
    dependabot = REPO_ROOT / ".github" / "dependabot.yml"
    if not dependabot.parent.is_dir():
        pytest.skip("dependabot.yml is only present in a repository checkout")
    text = dependabot.read_text(encoding="utf-8")
    assert 'package-ecosystem: "github-actions"' in text
    assert 'package-ecosystem: "pip"' in text
    assert 'interval: "weekly"' in text
    assert "groups:" in text


def test_github_workflow_jobs_pin_the_runner_image():
    workflows = _workflows()
    assert {"ci.yml", "docs.yml", "release.yml"} <= set(workflows)
    for name, workflow in workflows.items():
        assert workflow["jobs"], f"{name} has no jobs"
        for job_name, job in workflow["jobs"].items():
            if "uses" in job:
                assert job["uses"].startswith("./.github/workflows/"), f"{name}: {job_name}"
                assert "runs-on" not in job, f"{name}: {job_name} calls a workflow"
                continue
            runner = job.get("runs-on")
            assert isinstance(runner, str), f"{name}: {job_name} needs one runs-on label"
            assert "-latest" not in runner, f"{name}: {job_name} runs on {runner}"
            if name in {"ci.yml", "docs.yml", "release.yml"}:
                assert runner == "ubuntu-24.04", f"{name}: {job_name} runs on {runner}"


def test_the_release_is_built_only_after_ci_passes():
    workflows = _workflows()
    ci, release = workflows["ci.yml"], workflows["release.yml"]
    assert "workflow_call" in _triggers(ci)
    jobs = release["jobs"]
    assert jobs["ci"]["uses"] == "./.github/workflows/ci.yml"
    assert _needs(jobs["ci"]) == []
    assert _needs(jobs["build"]) == ["ci"]
    for name in ("publish-pypi", "publish-testpypi"):
        assert _needs(jobs[name]) == ["build"]
    for name in jobs:
        if name != "ci":
            assert _depends_on(jobs, name, "ci"), f"release.yml: {name} does not wait for CI"
    assert ci["concurrency"]["group"] != release["concurrency"]["group"], (
        "ci.yml is called by release.yml and sees the caller's github.workflow: "
        "identical concurrency groups would make the release run cancel itself"
    )


def test_a_release_tag_runs_ci_once():
    workflows = _workflows()
    ci_triggers = _triggers(workflows["ci.yml"])
    assert {"push", "pull_request", "workflow_dispatch", "workflow_call"} <= set(ci_triggers)
    ci_push = ci_triggers["push"]
    assert "tags" not in ci_push, (
        "release.yml calls ci.yml for a v* tag: a tags trigger here runs CI twice"
    )
    assert "main" in ci_push["branches"]
    assert "v*" in _triggers(workflows["release.yml"])["push"]["tags"]


def test_the_nox_test_cells_install_pyyaml_for_the_workflow_tests():
    noxfile = (REPO_ROOT / "noxfile.py").read_text(encoding="utf-8")
    tests_session = noxfile.split("\ndef tests(", 1)[1].split("\n@nox.session", 1)[0]
    assert '"PyYAML>=6"' in tests_session, "without PyYAML the workflow tests skip in every cell"


def test_ruff_is_bounded_and_enforces_formatting():
    noxfile = (REPO_ROOT / "noxfile.py").read_text(encoding="utf-8")
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    spec = re.search(r'(?m)^RUFF = "(ruff>=[\d.]+,<[\d.]+)"$', noxfile)
    assert spec is not None
    extra = re.search(r"(?m)^test = \[(.*)\]$", pyproject)
    assert extra is not None
    assert f'"{spec[1]}"' in extra[1]
    assert 'session.run("ruff", "check", ".")' in noxfile
    assert 'session.run("ruff", "format", "--check", ".")' in noxfile


def test_the_source_tree_is_ruff_formatted():
    if importlib.util.find_spec("ruff") is None:
        pytest.skip("ruff is not installed in this environment")
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "format", "--check", "--no-cache", "."],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
