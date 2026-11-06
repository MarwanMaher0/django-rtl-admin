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
nox                                      # every cell, then ruff
```

CI reads the cell list from the noxfile (`nox -l --json`) and runs every cell as a separate
job, so adding a version to `noxfile.py` is all that is needed to add it to CI. Every job
writes its coverage table to the job summary; the Python 3.13 / Django 5.2 job also uploads
the report as an artifact and publishes it to [Coveralls](https://coveralls.io/github/MarwanMaher0/django-rtl-admin),
which authenticates with the workflow's own `GITHUB_TOKEN` and needs no repository secret. CI
also runs ruff and checks that the wheel carries the templates, static files and translations.

### Browser tests

`tests/e2e/` opens the admin in a real Chromium, in Arabic and English, light and dark, at
360px and 1280px, and checks overflow, icon direction and mirrored layout. Each page's
screenshot is written to `test-artifacts/e2e/` (git-ignored) so you can look at what the
assertions saw. Without Playwright installed the directory is skipped.

```bash
nox -s e2e                               # newest Python/Django, installs Chromium itself
# or in your own virtualenv:
pip install -e ".[e2e]" && python -m playwright install chromium
RTL_ADMIN_E2E=1 pytest tests/e2e
```

CI runs them once, on the newest Python/Django pair, and uploads the screenshots as the
`e2e-screenshots` artifact even when a test fails.

## Style

- ruff, with the rules and line length in `pyproject.toml`.
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
secrets. The workflow builds the sdist and wheel once, runs `twine check`, keeps them as the
`dist` artifact, and then publishes that same artifact:

- **Pushing a `v*` tag** publishes to PyPI, through the `pypi` environment.
- **Running the workflow by hand** (Actions → Release → Run workflow) publishes to TestPyPI,
  through the `testpypi` environment. Use it to rehearse a release.

The publish step also uploads signed PEP 740 attestations for each file.

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

### Cut a release

1. On `main`, set `version` in `pyproject.toml` to the new version, and in `CHANGELOG.md`
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

   The build fails if the tag (without its `v`) differs from `version` in `pyproject.toml`.
   Approve the `pypi` deployment when GitHub asks, then check
   <https://pypi.org/project/django-rtl-admin/>.
4. Create a GitHub release from the tag, with the changelog section as its notes.

A version cannot be re-uploaded to PyPI, even after it is deleted. If something is wrong, fix
it and release the next patch version.
