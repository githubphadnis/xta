from sqlalchemy import Column, Integer, String, Float, Date
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