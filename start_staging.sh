#!/usr/bin/env bash

# =====================================================
# テスト環境（Render の staging サービス）の起動スクリプト
#
# 本番の start.sh との違い:
# - 定期処理（お出かけスケジューラー）は既定で動かさない
#   動かしたいときは STAGING_RUN_SCHEDULERS=true
# - 各アプリの初期データを用意する
# =====================================================

set -e

if [ "${APP_ENV:-}" != "staging" ]; then
    echo "APP_ENV=staging が設定されていません。本番では start.sh を使ってください。" >&2
    exit 1
fi

python manage.py migrate --noinput

python manage.py seed_master_data

python manage.py setup_news_defaults

if [ "${STAGING_RUN_SCHEDULERS:-}" = "true" ]; then
    python -u manage.py outings_scheduler &
fi

exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT:-10000}"
