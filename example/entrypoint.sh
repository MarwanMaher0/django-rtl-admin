#!/bin/sh
set -eu

case "${*:-}" in
    *gunicorn*|*runserver*)
        python manage.py migrate --no-input
        if [ "${RESET_DEMO_ON_STARTUP:-0}" = "1" ]; then
            python manage.py reset_demo
        else
            python -c "import django; django.setup(); from django.contrib.auth import get_user_model; from library.models import Book; User = get_user_model(); raise SystemExit(0 if User.objects.filter(username='demo').exists() and Book.objects.exists() else 1)" \
                || python manage.py reset_demo --no-flush
        fi

        if [ "${RESET_DEMO_INTERVAL_SECONDS:-0}" -gt 0 ] 2>/dev/null; then
            (
                while true; do
                    sleep "${RESET_DEMO_INTERVAL_SECONDS}"
                    python manage.py reset_demo || true
                done
            ) &
        fi
        ;;
esac

exec "$@"
