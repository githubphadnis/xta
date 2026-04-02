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


def test_dashboard_renders_richer_metrics():
    TestingSessionLocal = _setup_test_db()
    db = TestingSessionLocal()
    db.add_all(
        [
            Expense(
                owner_email="alice@example.com",
                vendor="Store A",
                amount=20.0,
                currency="EUR",
                base_currency_amount=20.0,
                base_currency="EUR",
                fx_rate=1.0,
                date=date.today(),
                category="Groceries",
                description="",
                source_type="manual",
            ),
            Expense(
                owner_email="alice@example.com",
                vendor="Store B",
                amount=30.0,
                currency="EUR",
                base_currency_amount=30.0,
                base_currency="EUR",
                fx_rate=1.0,
                date=date.today(),
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
    response = client.get("/", headers={"cf-access-authenticated-user-email": "alice@example.com"})
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "MoM (30d)" in response.text
    assert "12m Spend" in response.text
    assert "12m Monthly Avg" in response.text
    assert "Version 0.1.0" in response.text
