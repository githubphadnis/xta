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


def test_expenses_page_and_chart_data_support_date_filters():
    TestingSessionLocal = _setup_test_db()
    db = TestingSessionLocal()
    db.add_all(
        [
            Expense(
                owner_email="alice@example.com",
                vendor="Store A",
                amount=11.0,
                currency="EUR",
                base_currency_amount=11.0,
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
                amount=22.0,
                currency="EUR",
                base_currency_amount=22.0,
                base_currency="EUR",
                fx_rate=1.0,
                date=date(2026, 2, 1),
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

    page_response = client.get("/expenses?month=2026-02", headers=headers)
    assert page_response.status_code == 200
    assert "Store B" in page_response.text
    assert "Store A" not in page_response.text

    chart_response = client.get("/api/expenses/chart-data?month=2026-02", headers=headers)
    app.dependency_overrides.clear()
    assert chart_response.status_code == 200
    payload = chart_response.json()
    assert payload["vendors"]["labels"] == ["Store B"]
    assert payload["vendors"]["data"] == [22.0]


def test_expenses_page_supports_explicit_date_range():
    TestingSessionLocal = _setup_test_db()
    db = TestingSessionLocal()
    db.add_all(
        [
            Expense(
                owner_email="alice@example.com",
                vendor="Store Jan",
                amount=11.0,
                currency="EUR",
                base_currency_amount=11.0,
                base_currency="EUR",
                fx_rate=1.0,
                date=date(2026, 1, 15),
                category="Groceries",
                description="",
                source_type="manual",
            ),
            Expense(
                owner_email="alice@example.com",
                vendor="Store Feb",
                amount=22.0,
                currency="EUR",
                base_currency_amount=22.0,
                base_currency="EUR",
                fx_rate=1.0,
                date=date(2026, 2, 15),
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
    response = client.get(
        "/expenses?start_date=2026-02-01&end_date=2026-02-28",
        headers=headers,
    )
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert "Store Feb" in response.text
    assert "Store Jan" not in response.text
