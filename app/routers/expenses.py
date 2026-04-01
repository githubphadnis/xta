from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime

from app.core.config import settings
from app.core.security import require_user_email
from app.db.session import get_db
from app.models.expense import Expense
from app.services.finance import fx_service

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.post("/expenses/confirm")
async def confirm_expense(
    request: Request,
    vendor: str = Form(...),
    amount: float = Form(...),
    date: str = Form(...),
    currency: str = Form(...),
    category: str = Form(...),  # <--- NEW: Accepting Category from the form
    receipt_url: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        parsed_date = datetime.now().date()
    user_email = require_user_email(request)
    normalized_currency = (currency or settings.BASE_CURRENCY).upper()
    base_currency_amount, fx_rate = fx_service.convert_to_base(amount, normalized_currency, parsed_date)

    new_expense = Expense(
        owner_email=user_email,
        vendor=vendor,
        amount=amount,
        date=parsed_date,
        currency=normalized_currency,
        base_currency_amount=base_currency_amount,
        base_currency=settings.BASE_CURRENCY,
        fx_rate=fx_rate,
        receipt_url=receipt_url,
        category=category,  # <--- NEW: Saving the AI's category to the database
        description=f"Receipt from {vendor}"
    )
    db.add(new_expense)
    db.commit()
    db.refresh(new_expense)
    return {"status": "success", "id": new_expense.id}

@router.get("/expenses", response_class=HTMLResponse)
async def my_expenses(request: Request, db: Session = Depends(get_db)):
    user_email = require_user_email(request)
    expenses = (
        db.query(Expense)
        .filter(Expense.owner_email == user_email)
        .order_by(Expense.date.desc())
        .all()
    )
    return templates.TemplateResponse(
        request=request,
        name="expenses.html",
        context={
            "expenses": expenses,
            "base_currency": settings.BASE_CURRENCY,
        },
    )

@router.delete("/expenses/{expense_id}")
async def delete_expense(expense_id: int, request: Request, db: Session = Depends(get_db)):
    user_email = require_user_email(request)
    expense = db.query(Expense).filter(Expense.id == expense_id, Expense.owner_email == user_email).first()
    if expense:
        db.delete(expense)
        db.commit()
        return ""
    raise HTTPException(status_code=404, detail="Expense not found")

@router.get("/api/expenses/chart-data")
async def get_chart_data(request: Request, db: Session = Depends(get_db)):
    user_email = require_user_email(request)
    # 1. Category Breakdown (Doughnut)
    cat_data = (
        db.query(Expense.category, func.sum(Expense.base_currency_amount))
        .filter(Expense.owner_email == user_email)
        .group_by(Expense.category)
        .all()
    )
    
    # 2. Top 5 Vendors (Bar)
    vendor_data = (
        db.query(Expense.vendor, func.sum(Expense.base_currency_amount))
        .filter(Expense.owner_email == user_email)
        .group_by(Expense.vendor)
        .order_by(func.sum(Expense.base_currency_amount).desc())
        .limit(5)
        .all()
    )
    
    # 3. Monthly Trend (Line) - PostgreSQL specific grouping
    trend_data = (
        db.query(func.to_char(Expense.date, 'YYYY-MM').label('month'), func.sum(Expense.base_currency_amount))
        .filter(Expense.owner_email == user_email)
        .group_by('month')
        .order_by('month')
        .limit(12)
        .all()
    )

    # Fallback if DB is empty
    if not cat_data:
        return {
            "categories": {"labels": ["No Data"], "data": [1]},
            "vendors": {"labels": ["No Data"], "data": [1]},
            "trend": {"labels": ["No Data"], "data": [1]}
        }

    return {
        "categories": {
            "labels": [row[0] for row in cat_data],
            "data": [float(row[1]) for row in cat_data]
        },
        "vendors": {
            "labels": [row[0] for row in vendor_data],
            "data": [float(row[1]) for row in vendor_data]
        },
        "trend": {
            "labels": [row[0] for row in trend_data],
            "data": [float(row[1]) for row in trend_data]
        },
        "base_currency": settings.BASE_CURRENCY,
    }