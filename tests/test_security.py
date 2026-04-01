from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import ANONYMOUS_USER_EMAIL, require_user_email


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/direct")
    def direct(request: Request):
        return {"email": require_user_email(request)}

    return app


def test_require_user_email_accepts_cloudflare_header():
    app = _build_app()
    client = TestClient(app)
    response = client.get("/direct", headers={"cf-access-authenticated-user-email": "User@Example.COM"})
    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"


def test_require_user_email_rejects_when_required():
    app = _build_app()
    client = TestClient(app)
    original = settings.AUTH_REQUIRED
    settings.AUTH_REQUIRED = True
    try:
        response = client.get("/direct")
        assert response.status_code == 401
    finally:
        settings.AUTH_REQUIRED = original


def test_require_user_email_uses_anonymous_when_optional():
    app = _build_app()
    client = TestClient(app)
    original = settings.AUTH_REQUIRED
    settings.AUTH_REQUIRED = False
    try:
        response = client.get("/direct")
        assert response.status_code == 200
        assert response.json()["email"] == ANONYMOUS_USER_EMAIL
    finally:
        settings.AUTH_REQUIRED = original
