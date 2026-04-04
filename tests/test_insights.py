from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.expense import Expense


def _setup_test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return TestingSessionLocal


def test_insights_ask_save_and_pin_flow():
    TestingSessionLocal = _setup_test_db()
    db = TestingSessionLocal()
    db.add_all(
        [
            Expense(
                owner_email="alice@example.com",
                vendor="Store A",
                amount=15.0,
                currency="EUR",
                base_currency_amount=15.0,
                base_currency="EUR",
                fx_rate=1.0,
                date=date(2026, 1, 1),
                category="Groceries",
                description="",
                source_type="manual",
            ),
            Expense(
                owner_email="alice@example.com",
                vendor="Store B",
                amount=35.0,
                currency="EUR",
                base_currency_amount=35.0,
                base_currency="EUR",
                fx_rate=1.0,
                date=date(2026, 1, 2),
                category="Dining",
                description="",
                source_type="manual",
            ),
        ]
    )
    db.commit()
    db.close()

    def override_get_db():
        test_db = TestingSessionLocal()
        try:
            yield test_db
        finally:
            test_db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    headers = {"cf-access-authenticated-user-email": "alice@example.com"}

    ask_response = client.post(
        "/api/insights/ask",
        data={"question": "What is my biggest spend pot?"},
        headers=headers,
    )
    assert ask_response.status_code == 200
    ask_payload = ask_response.json()
    assert ask_payload["chart"]["labels"]
    assert ask_payload["sql"]

    save_response = client.post(
        "/api/insights/save",
        data={
            "name": "Biggest Spend",
            "question": ask_payload["question"],
            "sql_query": ask_payload["sql"],
            "chart_type": ask_payload["chart"]["type"],
        },
        headers=headers,
    )
    assert save_response.status_code == 200
    saved_id = save_response.json()["id"]

    pin_response = client.post(f"/api/insights/{saved_id}/pin", headers=headers)
    assert pin_response.status_code == 200

    list_response = client.get("/api/insights/saved", headers=headers)
    app.dependency_overrides.clear()
    assert list_response.status_code == 200
    rows = list_response.json()
    assert rows
    assert rows[0]["is_pinned"] is True


def test_delete_saved_query():
    TestingSessionLocal = _setup_test_db()
    db = TestingSessionLocal()
    db.add(
        Expense(
            owner_email="alice@example.com",
            vendor="Store A",
            amount=10.0,
            currency="EUR",
            base_currency_amount=10.0,
            base_currency="EUR",
            fx_rate=1.0,
            date=date(2026, 1, 1),
            category="Groceries",
            description="",
            source_type="manual",
        )
    )
    db.commit()
    db.close()

    def override_get_db():
        test_db = TestingSessionLocal()
        try:
            yield test_db
        finally:
            test_db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    headers = {"cf-access-authenticated-user-email": "alice@example.com"}

    ask_response = client.post(
        "/api/insights/ask",
        data={"question": "What is my biggest spend pot?"},
        headers=headers,
    )
    ask_payload = ask_response.json()
    save_response = client.post(
        "/api/insights/save",
        data={
            "name": "To Delete",
            "question": ask_payload["question"],
            "sql_query": ask_payload["sql"],
            "chart_type": ask_payload["chart"]["type"],
        },
        headers=headers,
    )
    saved_id = save_response.json()["id"]
    delete_response = client.delete(f"/api/insights/{saved_id}", headers=headers)
    assert delete_response.status_code == 200

    list_response = client.get("/api/insights/saved", headers=headers)
    assert list_response.status_code == 200
    rows = list_response.json()
    assert all(row["id"] != saved_id for row in rows)

    second_delete = client.delete(f"/api/insights/{saved_id}", headers=headers)
    assert second_delete.status_code == 404
    app.dependency_overrides.clear()


def test_insights_intent_echoes_auto_when_not_provided():
    TestingSessionLocal = _setup_test_db()
    db = TestingSessionLocal()
    db.add(
        Expense(
            owner_email="alice@example.com",
            vendor="Store A",
            amount=10.0,
            currency="EUR",
            base_currency_amount=10.0,
            base_currency="EUR",
            fx_rate=1.0,
            date=date(2026, 1, 1),
            category="Groceries",
            description="",
            source_type="manual",
        )
    )
    db.commit()
    db.close()

    def override_get_db():
        test_db = TestingSessionLocal()
        try:
            yield test_db
        finally:
            test_db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    headers = {"cf-access-authenticated-user-email": "alice@example.com"}
    response = client.post("/api/insights/ask", data={"question": "show category split"}, headers=headers)
    app.dependency_overrides.clear()
    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "auto"
