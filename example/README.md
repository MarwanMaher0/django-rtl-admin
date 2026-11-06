# django-rtl-admin Example & Live Demo

This directory contains a runnable Django project showcasing `django-rtl-admin`
in English (`en`), Arabic (`ar`), Arabic — Egypt (`ar-eg`), and Hebrew (`he`).
It is ready to run locally with `manage.py runserver`, inside Docker with
Gunicorn and WhiteNoise, or deployed to Fly.io / Render as a public read-only
live demo.

## Quick start (local)

From the repository root (no environment variables are required for local development):

```sh
python -m pip install -e ".[babel,demo]"
cd example
python manage.py reset_demo
python manage.py runserver
```

Or for local development with a full superuser account:

```sh
cd example
python manage.py migrate
python manage.py demodata
python manage.py runserver
```

Open <http://127.0.0.1:8000/admin/> and sign in with:

- **Username:** `demo`
- **Password:** `demo12345`

Use the language switcher in the header (or on the login page) to switch between
English, Arabic, Arabic (Egypt), and Hebrew.

## The demo user

When configured via `python manage.py reset_demo` (or `python manage.py demodata --read-only`),
`demo` (`demo` / `demo12345`) is a **read-only staff user** (`is_staff=True`,
`is_superuser=False`) in the `Demo Read-Only` group:

- Its permissions are limited strictly to `view_*` on the demo models
  (`library.Publisher`, `library.Book`, and `library.Chapter`).
- It cannot view `auth` users or groups (`/admin/auth/user/` and
  `/admin/auth/group/` return `403 Forbidden`).
- It cannot add, change, or delete any models.
- The **Change password** link in the admin header is hidden for the `demo`
  user, and the password change endpoints (`/admin/password_change/` and
  `/admin/password_change/done/`) are blocked with `403 Forbidden` only for the
  shared `demo` account so visitors cannot lock out the demo credentials; other
  staff users still see the header link and can change their own password.

## Management commands

| Command | Behavior |
| --- | --- |
| `python manage.py reset_demo` (or `resetdemo`) | Runs migrations, flushes the database, reloads sample bilingual records (`Publisher`, `Book`, `Chapter`), and configures `demo` (`demo` / `demo12345`) as a **read-only staff user** (`is_staff=True`, `is_superuser=False`) in the `Demo Read-Only` group with `view_*` permissions only on the `library` demo models. |
| `python manage.py demodata` | Creates or updates `demo` as a superuser (or a read-only staff user with `--read-only`) and upserts the sample bilingual records without flushing the database. |

## Environment variables

`example/config/settings.py` is configured via environment variables. `DEBUG`
defaults to `False` unless explicitly enabled and never enables `LOCAL_DEV` on
its own. `DJANGO_ENV` defaults to `production` regardless of `DEBUG`;
`example/manage.py` sets `DJANGO_ENV=development` by default so local commands
(`python manage.py runserver`) have `LOCAL_DEV=True` when no deployment
environment variables are set, working with zero environment variables and
serving the admin static files automatically. Outside local development
(`LOCAL_DEV=False` — including when `DJANGO_ENV=production`, when any deployment
environment variable such as `RENDER`, `FLY_APP_NAME`, `PORT`, `DATABASE_URL`,
`ALLOWED_HOSTS`, or `CSRF_TRUSTED_ORIGINS` is set, or whenever any WSGI/ASGI
server or `get_wsgi_application()` / `get_asgi_application()` imports
`config.settings` without `manage.py`), `example/config/settings.py` requires
`SECRET_KEY` to be set to a strong, non-default value (never
`django-insecure-*`) or fails at startup with `ImproperlyConfigured`, and
`example/config/urls.py` never mounts Django's insecure static-file fallback
view:

| Variable | Default | Purpose |
| --- | --- | --- |
| `SECRET_KEY` | Local dev fallback *(only when `LOCAL_DEV=True`)* | Django secret key (`DJANGO_SECRET_KEY` is also accepted). Required whenever `LOCAL_DEV=False` (production and all WSGI/ASGI servers, regardless of `DEBUG`). |
| `DJANGO_ENV` | `production` (`development` via `manage.py`) | Explicit environment mode (`development`, `dev`, `local`, or `production`). `LOCAL_DEV` is `True` only when `DJANGO_ENV` is `development`/`dev`/`local` and no deployment environment variables are set. |
| `DEBUG` | `False` | Off unless set to `1`, `true`, `yes`, or `on`. |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,[::1],.localhost` | Comma-separated list of allowed HTTP `Host` headers. |
| `CSRF_TRUSTED_ORIGINS` | *(empty)* | Comma-separated list of trusted origins (e.g. `https://django-rtl-admin-demo.fly.dev`). |
| `DATABASE_URL` | `sqlite:///<BASE_DIR>/db.sqlite3` | Database URL (`sqlite:////data/db.sqlite3` or `postgres://...`; `psycopg[binary]` is included in `requirements.txt`). |
| `PORT` | `8000` | HTTP port bound by Gunicorn in Docker. |
| `WEB_CONCURRENCY` | `2` | Number of Gunicorn worker processes. |
| `RESET_DEMO_ON_STARTUP` | `0` (`1` in `fly.toml`) | When set to `1`, `entrypoint.sh` runs `python manage.py reset_demo` on every container start. |
| `RESET_DEMO_INTERVAL_SECONDS` | `0` (`3600` in `fly.toml`) | Runs `python manage.py reset_demo` inside the web container every N seconds (`3600` = hourly) against the active `DATABASE_URL`. |

## Running with Docker

You can build the image either from the repository root (which installs the
local `django-rtl-admin` checkout) or from `example/`:

```sh
# From the repository root:
docker build -t django-rtl-admin-demo .

# Run the container:
docker run --rm -p 8000:8000 \
  -e SECRET_KEY="change-me-in-production" \
  -e ALLOWED_HOSTS="localhost,127.0.0.1" \
  django-rtl-admin-demo
```

Verify the running container:

```sh
curl -fsS http://127.0.0.1:8000/healthz/
curl -fsSI http://127.0.0.1:8000/admin/login/
```

## Deploying to Fly.io

From the repository root (using `fly.toml`):

```sh
fly launch --copy-config --no-deploy
fly volumes create demo_data --region fra --size 1
fly secrets set SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(50))')"
fly deploy
```

> **Note on `auto_stop_machines` and the hourly reset:** Because `fly.toml` sets
> `auto_stop_machines = "stop"` and `min_machines_running = 0`, the in-container
> `RESET_DEMO_INTERVAL_SECONDS = "3600"` background loop is lost whenever the
> Fly Machine auto-stops due to inactivity. `fly.toml` also sets
> `RESET_DEMO_ON_STARTUP = "1"` so `entrypoint.sh` runs `python manage.py reset_demo`
> whenever the machine auto-starts on the next request. If you want continuous
> hourly resets while idle, set `auto_stop_machines = "off"` and
> `min_machines_running = 1` in `fly.toml`.

## Deploying to Render

Use the root `render.yaml` Blueprint in the Render dashboard (**New →
Blueprint**). It provisions a shared Render PostgreSQL database
(`django-rtl-admin-demo-db`, `plan: free`, using `psycopg[binary]` from
`requirements.txt`), the Docker web service (`plan: free`,
`healthCheckPath: /healthz/`), and a single hourly cron job
(`schedule: "0 * * * *"`, `plan: starter` — Render Cron Jobs do not support a
`free` plan) that connects to the same shared `DATABASE_URL` and runs
`python manage.py reset_demo`.

## Scheduled demo resets

The demo database is reset on an **hourly schedule** (`0 * * * *` / every `3600`
seconds) against the database the web service actually uses:

- **In-container hourly loop (`RESET_DEMO_INTERVAL_SECONDS=3600`):** Configured
  in `fly.toml` alongside `RESET_DEMO_ON_STARTUP=1`; `entrypoint.sh` runs
  `python manage.py reset_demo` on machine startup and every 3600 seconds while
  the container is running against its active `DATABASE_URL` (`/data/db.sqlite3`).
- **Render Cron Job (`0 * * * *`):** `render.yaml` wires both the `web` service
  and the single `cron` service to the shared `django-rtl-admin-demo-db`
  PostgreSQL database via `fromDatabase`.
- **Docker host cron (`0 * * * *`):**

```sh
# Inside a running container or VM:
python manage.py reset_demo

# Or via Docker from the host cron (hourly at minute 0):
0 * * * * docker exec django-rtl-admin-demo python manage.py reset_demo >/dev/null 2>&1
```
