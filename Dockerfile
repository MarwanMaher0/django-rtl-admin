# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=config.settings \
    DEBUG=false \
    PORT=8000

RUN groupadd --system --gid 10001 appuser \
    && useradd --system --uid 10001 --gid appuser --home-dir /app --create-home appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /app /data

WORKDIR /app

COPY --chown=appuser:appuser . /tmp/build-context

RUN if [ -f /tmp/build-context/pyproject.toml ] && [ -d /tmp/build-context/example ]; then \
        pip install "/tmp/build-context[babel]" -r /tmp/build-context/example/requirements.txt \
        && cp -a /tmp/build-context/example/. /app/; \
    else \
        pip install \
            "django-rtl-admin[babel] @ https://github.com/MarwanMaher0/django-rtl-admin/archive/refs/heads/main.tar.gz" \
            -r /tmp/build-context/requirements.txt \
        && cp -a /tmp/build-context/. /app/; \
    fi \
    && rm -rf /tmp/build-context /app/db.sqlite3 /app/staticfiles \
    && chmod +x /app/entrypoint.sh \
    && chown -R appuser:appuser /app /data

USER appuser

RUN SECRET_KEY="build-only-collectstatic-secret-key" python manage.py collectstatic --no-input \
    && SECRET_KEY="build-only-collectstatic-secret-key" python manage.py reset_demo

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; port = os.environ.get('PORT', '8000'); urllib.request.urlopen(f'http://127.0.0.1:{port}/healthz/', timeout=3)"

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["sh", "-c", "exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers ${WEB_CONCURRENCY:-2} --access-logfile -"]
