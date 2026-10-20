
#!/usr/bin/env bash

set -e

# Keep glibc from holding on to freed memory in many arenas
# (the instance has only 512 MB).
export MALLOC_ARENA_MAX="${MALLOC_ARENA_MAX:-2}"

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

# One worker, replaced after a few hundred requests so its memory
# cannot keep creeping up. WEB_CONCURRENCY can override the count.
gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT:-10000}" \
    --workers "${WEB_CONCURRENCY:-1}" \
    --max-requests 500 \
    --max-requests-jitter 50 &

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
