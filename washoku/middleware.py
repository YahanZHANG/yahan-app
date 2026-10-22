"""
スイスで和食のページが開かれたときに、公開予約の時刻を過ぎた投稿を公開する。
予約の時刻からいちばん早く見る人のアクセスで公開されるので、定期実行はいらない。
"""

import time

from .models import publish_due_posts


# 何度も確かめないよう、1つのプロセスで最大1分に1回
CHECK_INTERVAL_SECONDS = 60

_last_check = 0.0


class PublishScheduledPostsMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        global _last_check

        if request.path.startswith("/washoku/"):

            now = time.monotonic()

            if now - _last_check >= CHECK_INTERVAL_SECONDS:
                _last_check = now
                publish_due_posts()

        return self.get_response(request)
