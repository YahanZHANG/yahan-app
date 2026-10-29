from django.db import migrations


def store_comments_to_reviews(apps, schema_editor):
    """
    お店のページに書かれたコメント (質問以外) を、お店の口コミ (投稿) に移す。
    返信・スタンプ・お知らせも口コミに付け替え、日時と写真もそのまま残す。
    感想 (よかった/ふつう/いまいち) はわからないので空のまま。
    """

    Comment = apps.get_model("washoku", "Comment")
    CommentReaction = apps.get_model("washoku", "CommentReaction")
    Notification = apps.get_model("washoku", "Notification")
    Post = apps.get_model("washoku", "Post")
    PostReaction = apps.get_model("washoku", "PostReaction")

    comments = Comment.objects.filter(store__isnull=False, parent__isnull=True, is_deleted=False).exclude(kind="question")

    for comment in comments.select_related("store"):

        post = Post.objects.create(
            kind="product",
            store=comment.store,
            title=comment.store.name,
            body=comment.body,
            author=comment.author,
            status="draft" if comment.is_hidden else "published",
            photo_1=comment.photo_url or "",
        )
        Post.objects.filter(pk=post.pk).update(created_at=comment.created_at)

        Comment.objects.filter(parent=comment).update(parent=None, store=None, post=post)

        for reaction in CommentReaction.objects.filter(comment=comment):
            PostReaction.objects.get_or_create(post=post, user=reaction.user, kind=reaction.kind)

        Notification.objects.filter(comment=comment).update(comment=None, post=post)

        comment.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("washoku", "0050_push_weekly"),
    ]

    operations = [
        migrations.RunPython(store_comments_to_reviews, migrations.RunPython.noop),
    ]
