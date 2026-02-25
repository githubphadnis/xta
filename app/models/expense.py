from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey
from sqlalchemy.orm import relationship
# 1. IMPORT BASE FROM SESSION (This now works because of step 1)
from app.db.session import Base

class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    vendor = Column(String, index=True)
    amount = Column(Float)
    currency = Column(String, default="EUR")
    date = Column(Date)
    category = Column(String, default="Uncategorized")
    description = Column(String, nullable=True)
    receipt_url = Column(String, nullable=True)

    # --- THE NEW LINK: Connects the receipt_details to this expense ---
    items = relationship("ExpenseItem", back_populates="expense", cascade="all, delete-orphan")


class ExpenseItem(Base):
    __tablename__ = "expense_items"

    id = Column(Integer, primary_key=True, index=True)
    # The ForeignKey links this item to a specific parent expense
    expense_id = Column(Integer, ForeignKey("expenses.id", ondelete="CASCADE"))
    
    name = Column(String, nullable=False)
    quantity = Column(Float, default=1.0)
    price = Column(Float, nullable=False)

    # The reverse link back to the parent Expense
    expense = relationship("Expense", back_populates="items")