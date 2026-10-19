#!/usr/bin/env bash

# =====================================================
# テスト環境（Render の staging サービス）の起動スクリプト
#
# Render の無料インスタンスを想定:
# - Shell が使えない → 必要な準備はここで自動実行する
# - ディスクは起動のたびに空になる → 毎回データを用意する
#
# 本番の start.sh との違い:
# - 定期処理（お出かけスケジューラー）は既定で動かさない
#   動かしたいときは STAGING_RUN_SCHEDULERS=true
# =====================================================

set -e

if [ "${APP_ENV:-}" != "staging" ]; then
    echo "APP_ENV=staging が設定されていません。本番では start.sh を使ってください。" >&2
    exit 1
fi

python manage.py migrate --noinput

python manage.py seed_master_data

python manage.py setup_news_defaults


# -----------------------------------------------------
# 管理者ユーザー
# DJANGO_SUPERUSER_USERNAME / DJANGO_SUPERUSER_EMAIL /
# DJANGO_SUPERUSER_PASSWORD が設定されていれば作る
# -----------------------------------------------------

if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ] \
    && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
    python manage.py createsuperuser --noinput \
        || echo "Superuser already exists."
fi


# -----------------------------------------------------
# SwissNews のニュースを取り込む（バックグラウンド）
# STAGING_LOAD_NEWS=true のときだけ。
# 起動のたびに OpenAI の料金がかかるので、
# 確認が終わったら変数を消すこと。
# -----------------------------------------------------

if [ "${STAGING_LOAD_NEWS:-}" = "true" ]; then
    python -u manage.py refresh_news \
        --period morning \
        --ai-limit "${STAGING_NEWS_AI_LIMIT:-60}" &
fi


if [ "${STAGING_RUN_SCHEDULERS:-}" = "true" ]; then
    python -u manage.py outings_scheduler &
fi

exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT:-10000}"
