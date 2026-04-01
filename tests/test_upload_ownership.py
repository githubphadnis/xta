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


def test_expenses_endpoint_is_scoped_to_user():
    TestingSessionLocal = _setup_test_db()
    db = TestingSessionLocal()
    db.add_all(
        [
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
            ),
            Expense(
                owner_email="bob@example.com",
                vendor="Store B",
                amount=20.0,
                currency="EUR",
                base_currency_amount=20.0,
                base_currency="EUR",
                fx_rate=1.0,
                date=date(2026, 1, 2),
                category="Dining",
                description="",
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
    response = client.get("/expenses", headers={"cf-access-authenticated-user-email": "alice@example.com"})
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "Store A" in response.text
    assert "Store B" not in response.text
