from fastapi import HTTPException, Request

from app.core.config import settings

ANONYMOUS_USER_EMAIL = "anonymous@local"
IDENTITY_HEADERS = (
    "cf-access-authenticated-user-email",
    "x-auth-request-email",
    "x-user-email",
)


def resolve_request_user_email(request: Request) -> str | None:
    for header in IDENTITY_HEADERS:
        value = request.headers.get(header)
        if value:
            return value.strip().lower()
    return None


def require_user_email(request: Request) -> str:
    user_email = resolve_request_user_email(request)
    if user_email:
        return user_email
    if settings.AUTH_REQUIRED:
        raise HTTPException(status_code=401, detail="Missing authenticated user identity header.")
    return ANONYMOUS_USER_EMAIL
