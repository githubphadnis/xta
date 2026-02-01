from sqlalchemy import Column, Integer, String, Float, Boolean, Date, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

# This Base class tracks all our models
Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    
    # Family Group Logic (allows "Profiles per member")
    # Users with the same family_id can see shared expenses
    family_id = Column(String, nullable=True, index=True) 

    # Relationship to expenses
    expenses = relationship("Expense", back_populates="owner")


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    
    # Financials (Original Currency)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), nullable=False) # e.g. "EUR", "USD"
    
    # Reporting (Converted)
    # We calculate this at entry time so dashboards are fast
    base_currency_amount = Column(Float, nullable=True)   
    
    # Details
    description = Column(String, nullable=True)
    category = Column(String, index=True, nullable=True)
    date_incurred = Column(Date, nullable=False)
    
    # Proof (Receipts)
    receipt_url = Column(String, nullable=True) # Path to the stored image
    
    # Privacy & Meta
    is_private = Column(Boolean, default=False) # If True, ignored by Family queries
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Owner Link
    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="expenses")