from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required

from django.db.models import Q

from django.http import (
    Http404,
)

from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)

from django.urls import reverse
from django.views.decorators.http import require_POST

from urllib.parse import urlencode

from .forms import ChatMessageForm

from .models import (
    ChatMessage,
    ChatConnection,
)


User = get_user_model()


# ==========================================
# ニックネーム取得
# ==========================================

def get_display_name(user):

    profile = getattr(
        user,
        "profile",
        None,
    )

    if profile:

        display_name = getattr(
            profile,
            "display_name",
            None,
        )

        if display_name:

            return display_name

    return user.username


# ==========================================
# 二人の友達関係を取得
# ==========================================

def get_connection(user_a, user_b):

    low_id = min(
        user_a.pk,
        user_b.pk,
    )

    high_id = max(
        user_a.pk,
        user_b.pk,
    )

    return ChatConnection.objects.filter(
        user_low_id=low_id,
        user_high_id=high_id,
    ).first()


# ==========================================
# 二人のメッセージを取得
# ==========================================

def get_conversation(user_a, user_b):

    return ChatMessage.objects.filter(

        Q(
            sender=user_a,
            recipient=user_b,
        )

        |

        Q(
            sender=user_b,
            recipient=user_a,
        )

    )


# ==========================================
# チャット一覧
# ==========================================

@login_required
def chat_list(request):

    current_user = request.user

    search_query = (
        request.GET.get("q", "")
        .strip()[:80]
    )

    # 自分が含まれる友達関係のみ

    connections = (

        ChatConnection.objects.filter(

            Q(user_low=current_user)

            |

            Q(user_high=current_user),

            status=ChatConnection.Status.ACCEPTED,

        )

        .select_related(
            "user_low",
            "user_high",
        )

    )

    chat_users = []

    for connection in connections:

        other_user = connection.other_user(
            current_user
        )

        if not other_user.is_active:
            continue

        display_name = get_display_name(
            other_user
        )

        # 友達一覧内で検索

        if search_query:

            matches_name = (
                search_query.casefold()
                in display_name.casefold()
            )

            matches_id = (
                search_query
                in str(other_user.pk)
            )

            if not (
                matches_name
                or matches_id
            ):
                continue

        conversation = get_conversation(
            current_user,
            other_user,
        )

        last_message = (

            conversation.order_by(
                "-created_at",
                "-pk",
            )

            .first()

        )

        unread_count = (

            ChatMessage.objects.filter(

                sender=other_user,

                recipient=current_user,

                is_read=False,

            ).count()

        )

        chat_users.append({

            "user": other_user,

            "display_name": display_name,

            "last_message": last_message,

            "unread_count": unread_count,

            "is_pinned": (
                connection.is_pinned_by(
                    current_user
                )
            ),

        })

    # ピン留め → 最近のメッセージ順

    chat_users.sort(

        key=lambda item: (

            item["is_pinned"],

            (
                item["last_message"]
                .created_at.timestamp()
            )

            if item["last_message"]

            else 0,

        ),

        reverse=True,

    )

    # --------------------------------------
    # 受信した友達申請
    # --------------------------------------

    pending_connections = (

        ChatConnection.objects.filter(

            Q(user_low=current_user)

            |

            Q(user_high=current_user),

            status=ChatConnection.Status.PENDING,

        )

        .exclude(
            requested_by=current_user,
        )

        .select_related(
            "requested_by",
        )

        .order_by(
            "-created_at",
        )

    )

    pending_requests = []

    for connection in pending_connections:

        pending_requests.append({

            "connection": connection,

            "sender": connection.requested_by,

            "display_name": get_display_name(
                connection.requested_by
            ),

        })

    return render(

        request,

        "chat/chat_list.html",

        {

            "chat_users": chat_users,

            "pending_requests": pending_requests,

            "search_query": search_query,

        },

    )


# ==========================================
# ログインIDによる友達検索
# ==========================================

@login_required
def chat_add(request):

    search_login_id = (
        request.GET.get("login_id", "")
        .strip()[:150]
    )

    searched = (
        "login_id" in request.GET
    )

    found_user = None

    connection = None

    is_self = False

    # ログインIDの完全一致検索

    if search_login_id:

        found_user = (

            User.objects.filter(

                is_active=True,

                **{
                    User.USERNAME_FIELD:
                    search_login_id
                },

            ).first()

        )

    if found_user:

        is_self = (
            found_user.pk
            == request.user.pk
        )

        if not is_self:

            connection = get_connection(
                request.user,
                found_user,
            )

    return render(

        request,

        "chat/chat_add.html",

        {

            "search_login_id": search_login_id,

            "searched": searched,

            "found_user": found_user,

            "connection": connection,

            "is_self": is_self,

            "display_name": (

                get_display_name(found_user)

                if found_user

                else ""

            ),

        },

    )

# ==========================================
# 友達申請を送信
# ==========================================

@login_required
@require_POST
def friend_request(request, user_id):

    other_user = get_object_or_404(

        User,

        pk=user_id,

        is_active=True,

    )

    if other_user.pk == request.user.pk:

        raise Http404()

    low_id = min(
        request.user.pk,
        other_user.pk,
    )

    high_id = max(
        request.user.pk,
        other_user.pk,
    )

    # 同じ二人の申請を重複作成しない

    ChatConnection.objects.get_or_create(

        user_low_id=low_id,

        user_high_id=high_id,

        defaults={

            "requested_by": request.user,

            "status": (
                ChatConnection.Status.PENDING
            ),

        },

    )

    url = reverse(
        "chat:add"
    )

    query = urlencode({
        "id": other_user.pk,
    })

    return redirect(
        f"{url}?{query}"
    )


# ==========================================
# 友達申請への返答
# ==========================================

@login_required
@require_POST
def friend_decision(
    request,
    connection_id,
):

    action = request.POST.get(
        "action"
    )

    if action not in [
        "accept",
        "decline",
    ]:

        raise Http404()

    current_user = request.user

    connection = get_object_or_404(

        ChatConnection.objects.filter(

            Q(user_low=current_user)

            |

            Q(user_high=current_user),

            status=ChatConnection.Status.PENDING,

        ).exclude(

            requested_by=current_user,

        ),

        pk=connection_id,

    )

    if action == "accept":

        new_status = (
            ChatConnection.Status.ACCEPTED
        )

    else:

        new_status = (
            ChatConnection.Status.DECLINED
        )

    ChatConnection.objects.filter(

        pk=connection.pk,

        status=ChatConnection.Status.PENDING,

    ).update(

        status=new_status,

    )

    return redirect(
        "chat:list"
    )


# ==========================================
# ピン留め ON / OFF
# ==========================================

@login_required
@require_POST
def chat_pin(request, user_id):

    other_user = get_object_or_404(

        User,

        pk=user_id,

        is_active=True,

    )

    connection = get_connection(
        request.user,
        other_user,
    )

    if (
        not connection
        or connection.status
        != ChatConnection.Status.ACCEPTED
    ):

        raise Http404()

    if (
        connection.user_low_id
        == request.user.pk
    ):

        connection.pinned_low = (
            not connection.pinned_low
        )

        connection.save(
            update_fields=[
                "pinned_low",
                "updated_at",
            ]
        )

    else:

        connection.pinned_high = (
            not connection.pinned_high
        )

        connection.save(
            update_fields=[
                "pinned_high",
                "updated_at",
            ]
        )

    return redirect(
        "chat:list"
    )


# ==========================================
# 個別チャット
# ==========================================

@login_required
def chat_room(request, user_id):

    other_user = get_object_or_404(

        User,

        pk=user_id,

        is_active=True,

    )

    # --------------------------------------
    # 友達関係を確認
    # --------------------------------------

    connection = get_connection(
        request.user,
        other_user,
    )

    if (
        not connection
        or connection.status
        != ChatConnection.Status.ACCEPTED
    ):

        raise Http404(
            "友達になってからチャットできるよ。"
        )

    # --------------------------------------
    # メッセージ送信
    # --------------------------------------

    if request.method == "POST":

        form = ChatMessageForm(
            request.POST
        )

        if form.is_valid():

            message = form.save(
                commit=False
            )

            message.sender = (
                request.user
            )

            message.recipient = (
                other_user
            )

            message.save()

            return redirect(

                "chat:room",

                user_id=other_user.pk,

            )

    else:

        form = ChatMessageForm()

    # --------------------------------------
    # 受信メッセージを既読にする
    # --------------------------------------

    if request.method == "GET":

        ChatMessage.objects.filter(

            sender=other_user,

            recipient=request.user,

            is_read=False,

        ).update(

            is_read=True,

        )

    # --------------------------------------
    # メッセージ履歴
    # --------------------------------------

    conversation = get_conversation(

        request.user,

        other_user,

    )

    recent_messages = list(

        conversation.order_by(

            "-created_at",

            "-pk",

        )[:100]

    )

    recent_messages.reverse()

    chat_messages = []

    for message in recent_messages:

        chat_messages.append({

            "message": message,

            "is_mine": (
                message.sender_id
                == request.user.pk
            ),

        })

    return render(

        request,

        "chat/chat_room.html",

        {

            "other_user": other_user,

            "other_display_name": (
                get_display_name(
                    other_user
                )
            ),

            "chat_messages": (
                chat_messages
            ),

            "form": form,

        },

    )