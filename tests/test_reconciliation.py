from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.expense import Expense
from app.routers.upload import _upsert_receipt_with_items


def _setup_test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return TestingSessionLocal


def test_receipt_upserts_statement_and_attaches_items():
    TestingSessionLocal = _setup_test_db()
    db = TestingSessionLocal()
    statement = Expense(
        owner_email="user@example.com",
        vendor="Store",
        amount=42.0,
        currency="EUR",
        base_currency_amount=42.0,
        base_currency="EUR",
        fx_rate=1.0,
        date=date(2026, 2, 1),
        category="Other",
        description="Bank Statement Import",
        source_type="statement",
    )
    db.add(statement)
    db.commit()
    db.refresh(statement)

    expense, attached_items, is_duplicate = _upsert_receipt_with_items(
        db=db,
        user_email="user@example.com",
        vendor="Store",
        parsed_date=date(2026, 2, 1),
        amount=42.0,
        currency="EUR",
        base_currency_amount=42.0,
        fx_rate=1.0,
        extracted_data={
            "category": "Groceries",
            "description": "Receipt import",
            "items": [{"name": "Bread", "quantity": 1, "price": 2.5}],
        },
    )
    db.commit()
    db.refresh(expense)

    assert not is_duplicate
    assert attached_items == 1
    assert expense.id == statement.id
    assert expense.source_type == "receipt"
    assert expense.category == "Groceries"
    assert len(expense.items) == 1
    assert expense.items[0].name == "Bread"

    db.close()
