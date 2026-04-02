from fastapi.testclient import TestClient

from app.main import app


def test_health_includes_version_and_base_currency():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code in {200, 503}
    payload = response.json()
    assert "version" in payload
    assert "base_currency" in payload
