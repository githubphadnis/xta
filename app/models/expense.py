from sqlalchemy import Column, Date, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.session import Base


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    owner_email = Column(String, index=True, nullable=False)
    vendor = Column(String, index=True, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), nullable=False, default="EUR")
    base_currency_amount = Column(Float, nullable=False)
    base_currency = Column(String(3), nullable=False, default="EUR")
    fx_rate = Column(Float, nullable=False, default=1.0)
    date = Column(Date, index=True, nullable=False)
    category = Column(String, default="Uncategorized")
    description = Column(String, nullable=True)
    receipt_url = Column(String, nullable=True)
    source_type = Column(String, nullable=False, default="manual")

    items = relationship("ExpenseItem", back_populates="expense", cascade="all, delete-orphan")


class ExpenseItem(Base):
    __tablename__ = "expense_items"

    id = Column(Integer, primary_key=True, index=True)
    expense_id = Column(Integer, ForeignKey("expenses.id", ondelete="CASCADE"))
    name = Column(String, nullable=False)
    quantity = Column(Float, default=1.0)
    price = Column(Float, nullable=False)

    expense = relationship("Expense", back_populates="items")