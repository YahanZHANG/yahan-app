
#!/usr/bin/env bash

set -e

# =====================================================
# Database initialization
# =====================================================

python manage.py migrate --noinput

python manage.py seed_master_data


# =====================================================
# Start Outings scheduler
# =====================================================

python -u manage.py outings_scheduler &

SCHEDULER_PID=$!


# =====================================================
# Start Gunicorn
# =====================================================

gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT:-10000}" &

WEB_PID=$!


# =====================================================
# Graceful shutdown
# =====================================================

cleanup() {
    trap - TERM INT

    kill "$WEB_PID" "$SCHEDULER_PID" 2>/dev/null || true

    wait "$WEB_PID" 2>/dev/null || true
    wait "$SCHEDULER_PID" 2>/dev/null || true
}

trap cleanup TERM INT

# If either process exits, shut down the other.
set +e
wait -n "$WEB_PID" "$SCHEDULER_PID"
EXIT_CODE=$?

cleanup

exit "$EXIT_CODE"
