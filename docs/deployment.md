# Live demo and deployment

The repository ships a complete bilingual demo project under `example/` with
Arabic and English fields (`Publisher`, `Book`, and `Chapter`), `BidiSafeAdminMixin`
configured on the changelists, locale-aware currency formatting (`EGP`), and the
header/login language switcher enabled for English (`en`), Arabic (`ar`),
Arabic — Egypt (`ar-eg`), and Hebrew (`he`).

---

## Running the demo locally

From the repository root (no environment variables required for local development):

```sh
python -m pip install -e ".[babel,demo]"
cd example
python manage.py reset_demo
python manage.py runserver
```

Open `http://127.0.0.1:8000/admin/` and sign in with:

- **Username:** `demo`
- **Password:** `demo12345`

### The demo user

The `example/` project provides two management commands for seeding data and configuring [the demo user](#the-demo-user):

- `python manage.py reset_demo` (alias: `resetdemo`) runs migrations, flushes the
  database, reloads the sample bilingual publishers, books, and chapters, and
  configures `demo` as a **read-only staff account** (`is_staff=True`,
  `is_superuser=False`) assigned to the `Demo Read-Only` group containing only
  `view_*` permissions for the demo models (`library.Publisher`, `library.Book`,
  and `library.Chapter`). The `demo` user cannot view `auth` users or groups,
  cannot add, modify, or delete records, has the **Change password** link hidden
  in the admin header, and is blocked from `/admin/password_change/` (`403 Forbidden`)
  so shared demo credentials cannot be rotated by visitors (other staff users see
  the link and can still change their own passwords).
- `python manage.py demodata` creates or updates `demo` as a full superuser (pass
  `--read-only` to create the view-only staff user instead) and upserts the
  sample records without flushing existing tables.

---

## Environment variables

`example/config/settings.py` reads its configuration from environment variables.
`DEBUG` defaults to `False` unless explicitly enabled and never enables
`LOCAL_DEV` on its own. `DJANGO_ENV` defaults to `production` regardless of
`DEBUG`; `example/manage.py` sets `DJANGO_ENV=development` by default so local
commands (`python manage.py runserver`) have `LOCAL_DEV=True` when no deployment
environment variables are present, allowing local runs with zero environment
variables and serving admin static files automatically. Outside local
development (`LOCAL_DEV=False` — including when `DJANGO_ENV=production`, when any
deployment environment variable such as `RENDER`, `FLY_APP_NAME`, `PORT`,
`DATABASE_URL`, `ALLOWED_HOSTS`, or `CSRF_TRUSTED_ORIGINS` is set, or whenever
any WSGI/ASGI server or `get_wsgi_application()` / `get_asgi_application()`
loads `config.settings` without `manage.py`), `example/config/settings.py`
requires `SECRET_KEY` to be set to a strong, non-default secret value (never
`django-insecure-*`) or raises `ImproperlyConfigured` at startup, and
`example/config/urls.py` never mounts Django's insecure static-file fallback
view:

| Variable | Default | Description |
| --- | --- | --- |
| `SECRET_KEY` | Local dev fallback *(only when `LOCAL_DEV=True`)* | Django cryptographic signing key. Required whenever `LOCAL_DEV=False` (production and all WSGI/ASGI servers, regardless of `DEBUG`); missing, default, or `django-insecure-*` keys raise `ImproperlyConfigured` in `config/settings.py` at startup. |
| `DJANGO_ENV` | `production` (`development` via `manage.py`) | Explicit environment mode (`development`, `dev`, `local`, or `production`). `LOCAL_DEV` is `True` only when `DJANGO_ENV` is `development`/`dev`/`local` and no deployment environment variables are set. |
| `DEBUG` | `False` | Off unless set to `1`, `true`, `yes`, or `on`. |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,[::1],.localhost` | Comma-separated hostnames allowed to serve the demo. |
| `CSRF_TRUSTED_ORIGINS` | *(empty)* | Comma-separated `https://` origins trusted for CSRF-protected POST requests (including `/i18n/setlang/` and `/admin/login/`). |
| `DATABASE_URL` | `sqlite:///<BASE_DIR>/db.sqlite3` | Database connection URL (`sqlite:////data/db.sqlite3` or `postgres://user:pass@host:5432/dbname`; `psycopg[binary]` is included in `example/requirements.txt`). |
| `PORT` | `8000` | Listener port used by Gunicorn inside the container. |
| `WEB_CONCURRENCY` | `2` | Number of Gunicorn worker processes. |
| `RESET_DEMO_ON_STARTUP` | `0` (`1` in `fly.toml`) | Set to `1` to force a full `reset_demo` flush on every container boot. |
| `RESET_DEMO_INTERVAL_SECONDS` | `0` (`3600` in `fly.toml`) | Interval in seconds for `entrypoint.sh` to run `python manage.py reset_demo` in the background against the web service's active `DATABASE_URL`. |

Static files are collected at image build time into `STATIC_ROOT` and served by
[WhiteNoise](https://whitenoise.readthedocs.io/) using
`CompressedStaticFilesStorage`.

---

## Running with Docker

Build and run the container from the repository root:

```sh
docker build -t django-rtl-admin-demo .
docker run --rm -p 8000:8000 \
  -e SECRET_KEY="replace-with-a-random-secret" \
  -e ALLOWED_HOSTS="localhost,127.0.0.1" \
  django-rtl-admin-demo
```

The `Dockerfile` uses `python:3.12-slim`, runs as a non-root user (`appuser`,
UID `10001`), runs `collectstatic` and `reset_demo` during the image build,
exposes `/healthz/` for container health checks, and starts Gunicorn via
`entrypoint.sh`.

Verify the container endpoints from another terminal:

```sh
# Health check
curl -fsS http://127.0.0.1:8000/healthz/

# Admin login page
curl -fsSI http://127.0.0.1:8000/admin/login/
```

---

## Deploying to Fly.io

A ready-to-use `fly.toml` is included at the repository root (and mirrored in
`example/fly.toml`):

```sh
# 1. Create the Fly app (do not deploy yet)
fly launch --copy-config --no-deploy

# 2. Create a persistent volume for the SQLite database
fly volumes create demo_data --region fra --size 1

# 3. Set a production secret key
fly secrets set SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(50))')"

# 4. Deploy
fly deploy
```

`fly.toml` mounts the `demo_data` volume at `/data`, sets
`DATABASE_URL="sqlite:////data/db.sqlite3"`, and configures an HTTP health check
against `GET /healthz/`.

!!! note "Auto-stopping Fly Machines and the hourly reset"
    Because `fly.toml` enables `auto_stop_machines = "stop"` with
    `min_machines_running = 0`, the in-container `RESET_DEMO_INTERVAL_SECONDS = "3600"`
    background timer only ticks while the Fly Machine is running and is lost
    whenever the machine auto-stops due to inactivity. To guarantee a clean state
    after an idle stop, `fly.toml` also sets `RESET_DEMO_ON_STARTUP = "1"` so
    `entrypoint.sh` runs `python manage.py reset_demo` whenever the machine
    auto-starts on the next request. If you need continuous wall-clock hourly
    resets even while idle, set `auto_stop_machines = "off"` and
    `min_machines_running = 1` in `fly.toml`.

---

## Deploying to Render

A `render.yaml` Blueprint is included at the repository root defining a shared
PostgreSQL database (`django-rtl-admin-demo-db`, `plan: free`, supported by
`psycopg[binary]` in `example/requirements.txt`), the Docker web service
(`django-rtl-admin-demo`, `plan: free`), and a single hourly cron job
(`django-rtl-admin-demo-reset`, `schedule: "0 * * * *"`, `plan: starter`) that
connects to the same shared `DATABASE_URL` and runs `python manage.py reset_demo`.

!!! note "Render Cron Job plan requirement"
    Render Cron Jobs (`type: cron`) do not offer a `free` plan—`plan: starter` is
    Render's minimum valid cron plan in `render.yaml`. If you want to deploy on
    Render using only free-tier resources, remove the `django-rtl-admin-demo-reset`
    cron service from `render.yaml` and add `RESET_DEMO_ON_STARTUP="1"` and
    `RESET_DEMO_INTERVAL_SECONDS="3600"` to the web service's `envVars`.

To deploy on Render:

1. Push the repository to GitHub.
2. In the Render dashboard, choose **New → Blueprint** and select the repository.
3. Render reads `render.yaml`, provisions `django-rtl-admin-demo-db`, wires its
   `connectionString` into `DATABASE_URL` for both the web service and the cron
   job, generates `SECRET_KEY`, and configures `/healthz/` as the health check
   path.

---

## Scheduling periodic demo resets

Even though [the demo user](#the-demo-user) is restricted to `view_*` permissions
for the `library` models and blocked from changing its password, running
`python manage.py reset_demo` on an **hourly schedule** (`0 * * * *` / every
`3600` seconds) guarantees that the database state, user credentials, and
permissions remain pristine. Crucially, the reset job must target the same
database (`DATABASE_URL`) that the web service actually serves:

### Option 1: Built-in container timer (`RESET_DEMO_INTERVAL_SECONDS`)

When `RESET_DEMO_INTERVAL_SECONDS` is set to a positive integer (configured to
`3600` — once every hour — in `fly.toml`), `entrypoint.sh` spawns a background
loop inside the running web container that executes
`python manage.py reset_demo` against the container's active `DATABASE_URL`
(such as the mounted `/data/db.sqlite3` volume on Fly.io). Note that on Fly.io
with `auto_stop_machines = "stop"`, this in-process timer stops when the machine
auto-stops; `fly.toml` pairs it with `RESET_DEMO_ON_STARTUP = "1"` so the
database is reset when the machine wakes back up.

### Option 2: System cron or container host timer (hourly: `0 * * * *`)

Run `reset_demo` inside the running web container so it resets the container's
active SQLite or PostgreSQL database:

```cron
0 * * * * docker exec django-rtl-admin-demo python manage.py reset_demo >/dev/null 2>&1
```

### Option 3: Render Cron Job with shared PostgreSQL database (`0 * * * *`)

`render.yaml` provisions a shared Render PostgreSQL database
(`django-rtl-admin-demo-db`) and passes its `connectionString` as `DATABASE_URL`
to both the `django-rtl-admin-demo` web service and the single
`django-rtl-admin-demo-reset` cron service (`schedule: "0 * * * *"`), ensuring
exactly one hourly reset runs against the database used by the web service.
