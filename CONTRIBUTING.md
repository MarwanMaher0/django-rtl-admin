# Contributing to django-rtl-admin

Bug reports (a screenshot of the admin in the wrong direction helps most), translations and
small, focused pull requests are all welcome.

## Set up

Python 3.10 or later.

```bash
git clone https://github.com/MarwanMaher0/django-rtl-admin.git
cd django-rtl-admin
python -m venv .venv && . .venv/bin/activate
pip install -e ".[test]"
```

To see the admin in both directions, use the example project and log in as `demo` / `demo12345`
(`DEBUG` is off by default, and local `runserver` serves the admin static files automatically
without needing `collectstatic` or extra environment variables):

```bash
cd example
python manage.py migrate
python manage.py demodata        # or: python manage.py reset_demo (read-only demo user)
python manage.py runserver
```

## Run the checks

```bash
pytest
ruff check .
ruff format --check .            # "ruff format ." rewrites the files
# type checking (mypy --strict with django-stubs, configured in pyproject.toml):
pip install -e ".[typecheck]" && mypy src
# the fallback path, without Babel:
pip uninstall -y Babel && pytest && pip install "Babel>=2.12"
# packaging:
pip install build twine && python -m build && python -m twine check dist/*
```

To test a different Python or Django than the one in your virtualenv, use nox. `noxfile.py`
has one `tests` cell for each Python/Django pair in
[Django's support matrix](https://docs.djangoproject.com/en/dev/faq/install/#what-python-version-can-i-use-with-django)
(Python 3.10-3.14, Django 4.2-6.1), plus a Python 3.12 / Django 5.2 cell without Babel. Each
cell runs pytest under coverage and prints the report. With [uv](https://docs.astral.sh/uv/) on
your PATH, interpreters you do not have are downloaded automatically.

```bash
pip install nox                          # or run it with: uvx nox
nox -l                                   # list the cells
nox -s "tests(py3.12-django5.2)"         # one cell
nox -s "tests(py3.12-django5.2)" -- -k bidi
nox -s lint                              # ruff check and ruff format --check
nox -s typecheck                         # mypy over src/
nox                                      # every cell, then ruff and mypy
```

The `test` extra installs ruff, and `nox -s lint` runs both `ruff check .` and
`ruff format --check .`. The formatter's output changes between ruff minor releases, so the
range is bounded (`RUFF` in `noxfile.py`, repeated in the `test` extra); widen both together and
run `ruff format .` when you move to a newer ruff. `tests/test_packaging.py` runs the same
format check, so a test cell fails too if a file drifts.

CI runs on every pull request and on every push to `main`, and can be started by hand. It has
no tag trigger of its own: for a `v*` tag the Release workflow calls it (see
[Releasing](#releasing)), so a release runs CI, and uploads coverage, once. CI reads the cell
list from the noxfile (`nox -l --json`) and runs every cell as a separate
job, so adding a version to `noxfile.py` is all that is needed to add it to CI. Coverage must
stay at or above `fail_under = 95` in `pyproject.toml` (`--fail-under=91` on the single
no-Babel cell, where Babel's branches in `formatting.py` do not run). Every job writes its
coverage table to the job summary; the Python 3.13 / Django 5.2 job also uploads the report as
an artifact and publishes it to [Coveralls](https://coveralls.io/github/MarwanMaher0/django-rtl-admin),
which authenticates with the workflow's own `GITHUB_TOKEN` and needs no repository secret. CI
also runs ruff (`nox -s lint`: lint rules and `ruff format --check`), runs mypy
(`nox -s typecheck`), checks that the wheel carries the templates,
static files, translations and `py.typed`, and builds the sdist (including `noxfile.py`,
`CONTRIBUTING.md` and `SECURITY.md`), unpacks it in a temporary directory, installs it and runs
`pytest -m "not e2e"` there.

All GitHub Actions in `.github/workflows/` are pinned by full 40-character commit SHA with a
`# vX.Y.Z` version comment, and `.github/dependabot.yml` groups weekly updates for
`github-actions` and `pip`. Every job in `ci.yml`, `docs.yml` and `release.yml` runs on
`ubuntu-24.04`, never `ubuntu-latest`, so a runner image change is a reviewed commit; a test
fails if a `-latest` label comes back. The workflow tests in `tests/test_packaging.py` parse
the YAML with PyYAML and are skipped without it. The nox test cells install it, which is what
makes those tests run in CI. It is also in the `test` extra, although nothing else needs it,
so that a plain `pytest` in a checkout set up with `pip install -e ".[test]"` runs them too
and a workflow mistake shows up before you push. In an unpacked sdist there is no
`.github/` directory, so they are skipped there whether PyYAML is installed or not.

### Browser tests

`tests/e2e/` opens the admin in a real Chromium, in Arabic and English, light and dark, at
360px and 1280px, and checks overflow, icon direction and mirrored layout. Each page's
screenshot is written to `test-artifacts/e2e/` (git-ignored) so you can look at what the
assertions saw. Without Playwright installed the directory is skipped.

`tests/e2e/test_computed_styles.py` reuses that suite for README defects 1, 2, 3, 4, 5, 6,
8 and selected rules from 10 (issue #3). It measures computed styles at 1280px in `ar-eg`
and `en`, with `ENABLE_CSS` enabled and disabled on the server. Expectations pin both
stock and package values (also at 800px for object-tools media-query coverage):
**all measured English computed properties must match stock**,
resolving logical float and text-alignment keywords to physical sides. RTL stock-parity
cases do not claim a failing negative control: sidebar chevrons already mirror through
Unicode; Django 6.0+ object-tools items retain stock inline-block/no-float layout with
zero margins on the first item; and Django 6.1+ already removed the help-text padding.
Defect 8 covers outer and inner help text and fieldset descriptions: `plaintext` is
RTL-only for these selectors, while English retains stock `unicode-bidi: isolate`.
Computed styles alone do not prove visual punctuation placement for defect 7 (labels)
or 9 (input paths); `test_change_form` separately checks label geometry, not path
punctuation. See [the coverage table](docs/rtl-defects.md#computed-style-coverage) for
exact test names, measured properties and limitations.

The two `test_issue_2_*` tests in the same module (issue #2) check `unicode-bidi: isolate` on
the object names the admin quotes: the message link, the change-form subtitle and the links
on both delete confirmation pages. They also run with `ISOLATE_TABLE_CELLS` off. The rule is
not tied to the direction, so English differs from stock there by design.

```bash
nox -s e2e                               # both Django 5.2 and newest (6.1), Python 3.14; installs Chromium
nox -s "e2e(py3.14-django5.2)" -- -k test_defect_1_addlink_icon_and_padding
# or in your own virtualenv (uses its installed Python/Django):
pip install -e ".[e2e]" && python -m playwright install chromium
RTL_ADMIN_E2E=1 pytest tests/e2e
```

CI derives its e2e matrix from `nox -l --json -s e2e`, runs both sessions, and uploads
screenshots even when a test fails. Artifact names are
`e2e-screenshots-${{ matrix.session }}` — for example,
`e2e-screenshots-e2e(py3.14-django5.2)` and `e2e-screenshots-e2e(py3.14-django6.1)`.

## Style

- ruff, with the rules and line length in `pyproject.toml`, for linting and for formatting:
  run `ruff format .` before you commit. CI rejects a file that `ruff format --check .` would
  change, including the Python code blocks in the Markdown files.
- The package ships `py.typed`, so its annotations are part of the public API. Annotate every
  new function and keep `nox -s typecheck` clean by fixing what mypy reports; a `# type: ignore`
  needs an error code and a comment saying why it cannot be avoided.
- HTML output escapes before it isolates. Follow `mark_isolated` and `mark_isolated_runs`, and
  give any new filter or display helper an autoescape test.
- `rtl-admin.css` uses logical properties. Physical rules are only for things that really are
  directional: sprite offsets, mirrored icons, chevrons.
- Every feature is opt-out through `RTL_ADMIN`. A new key goes in `conf.py` and in the README's
  settings table.
- Translations live in `src/django_rtl_admin/locale/`. Edit the `.po` file, run
  `django-admin compilemessages`, and commit both the `.po` and the `.mo`.
- Anything a user would notice gets a line in `CHANGELOG.md` under `## [Unreleased]`.

## Propose a change

1. For anything bigger than a small fix, open an issue first so the approach is agreed before
   you write code. The roadmap lives in the open issues.
2. Branch from `main`, keep the pull request to one change, and fill in the template.
3. CI must be green before review.

Security problems go through [SECURITY.md](SECURITY.md), not a public issue.

## Releasing

Maintainers only. `.github/workflows/release.yml` publishes with PyPI
[trusted publishing](https://docs.pypi.org/trusted-publishers/): GitHub Actions gets a
short-lived OIDC token for each run, so no API token is stored in the repository or its
secrets. The workflow first calls `ci.yml` (`workflow_call`) and waits for every CI job to
pass. Only then does it build the sdist and wheel once, run `twine check`, keep them as the
`dist` artifact, and publish that same artifact:

- **Pushing a `v*` tag** publishes to PyPI, through the `pypi` environment.
- **Running the workflow by hand** (Actions → Release → Run workflow) publishes to TestPyPI,
  through the `testpypi` environment. Use it to rehearse a release.

The publish step also uploads signed PEP 740 attestations for each file.

A called workflow sees the caller's `github.workflow`, so `ci.yml` prefixes its concurrency
group with `ci-`. Keep the two groups different: with the same group the release run would
cancel itself. `ci.yml` must not get a `tags` trigger back either: the Release workflow already
runs it for the tag, and a second trigger would run the whole matrix and the Coveralls upload
twice. Tests cover both.

### One-time setup

1. **GitHub environments.** In Settings → Environments, create `pypi` and `testpypi`. For
   `pypi`, add yourself as a required reviewer and limit deployments to tags matching `v*`, so
   a stray run cannot publish and every release waits for approval.
2. **PyPI.** Go to <https://pypi.org/manage/account/publishing/> (before the first release, as
   a "pending publisher"; after that, under the project's Settings → Publishing) and add a
   GitHub publisher:

   | Field             | Value              |
   | ----------------- | ------------------ |
   | PyPI project name | `django-rtl-admin` |
   | Owner             | `MarwanMaher0`     |
   | Repository name   | `django-rtl-admin` |
   | Workflow name     | `release.yml`      |
   | Environment name  | `pypi`             |

3. **TestPyPI.** TestPyPI is a separate site with separate accounts. Do the same at
   <https://test.pypi.org/manage/account/publishing/>, with the environment name `testpypi`.

The workflow file name and environment name must match exactly; if either is renamed, update
the publisher on PyPI and TestPyPI, or publishing fails with an `invalid-publisher` error.

### One-time setup for the documentation site

1. **GitHub Pages.** In Settings → Pages, under "Build and deployment", set **Source** to
   **GitHub Actions**. `.github/workflows/docs.yml` publishes the documentation with
   `actions/configure-pages` and `actions/deploy-pages`, and until this is set
   `configure-pages` fails because the repository has no Pages site. GitHub creates the
   `github-pages` environment itself on the first deployment. After that, every push to `main`
   builds the site with `mkdocs build --strict` and deploys it to
   <https://marwanmaher0.github.io/django-rtl-admin/>.
2. **Sitemap.** The documentation is a project site under `/django-rtl-admin/`, and crawlers
   only request `robots.txt` from the root of the host, so the site ships no `robots.txt`
   and cannot announce its sitemap there. Submit
   <https://marwanmaher0.github.io/django-rtl-admin/sitemap.xml> once in Google Search Console
   and Bing Webmaster Tools. Every page also links it with `<link rel="sitemap">`, and
   `llms.txt` lists it.

### Cut a release

1. On `main`, set `version` in `pyproject.toml` and `__version__` in
   `src/django_rtl_admin/__init__.py` to the new version, and in `CHANGELOG.md`
   rename `## [Unreleased]` to `## [X.Y.Z] - YYYY-MM-DD` and start a fresh `## [Unreleased]`
   above it. Commit, push, and wait for CI to go green.
2. Rehearse on TestPyPI: run the Release workflow by hand from `main`, then check the project
   page at <https://test.pypi.org/project/django-rtl-admin/> and that it installs:

   ```bash
   python -m venv /tmp/rehearsal && . /tmp/rehearsal/bin/activate
   pip install --index-url https://test.pypi.org/simple/ \
       --extra-index-url https://pypi.org/simple/ django-rtl-admin==X.Y.Z
   ```

   PyPI and TestPyPI never accept the same file twice. If the rehearsal needs another run,
   bump to a pre-release such as `X.Y.Zrc1` for it, or accept the "file already exists" error
   as proof that authentication worked.
3. Tag the release commit and push the tag:

   ```bash
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push origin vX.Y.Z
   ```

   The tag starts only the Release workflow, which runs the whole CI workflow on the tag
   first; nothing is built or published if a CI job fails.
   The build fails if the tag (without its `v`) differs from `version` in `pyproject.toml`.
   Approve the `pypi` deployment when GitHub asks, then check
   <https://pypi.org/project/django-rtl-admin/>.
4. Create a GitHub release from the tag, with the changelog section as its notes.

A version cannot be re-uploaded to PyPI, even after it is deleted. If something is wrong, fix
it and release the next patch version.
