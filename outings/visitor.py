
import uuid


COOKIE_NAME = "outings_visitor"


def get_visitor_id(request):
    raw = request.COOKIES.get(COOKIE_NAME)

    if raw:
        try:
            return uuid.UUID(raw)
        except (ValueError, AttributeError):
            pass

    return uuid.uuid4()


def set_visitor_cookie(request, response, visitor_id):
    if request.COOKIES.get(COOKIE_NAME) != str(visitor_id):
        response.set_cookie(
            COOKIE_NAME,
            str(visitor_id),
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            secure=request.is_secure(),
            samesite="Lax",
        )

    return response
