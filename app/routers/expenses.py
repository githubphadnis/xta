from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import require_user_email
from app.db.session import get_db
from app.models.expense import Expense
from app.models.saved_query import SavedQuery
from app.services.finance import fx_service

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _parse_filter_dates(month: str | None, start_date: str | None, end_date: str | None) -> tuple[date_type | None, date_type | None]:
    if month:
        year, month_num = month.split("-", 1)
        start = datetime.strptime(f"{year}-{month_num}-01", "%Y-%m-%d").date()
        if int(month_num) == 12:
            end = datetime.strptime(f"{int(year) + 1}-01-01", "%Y-%m-%d").date()
        else:
            end = datetime.strptime(f"{year}-{int(month_num) + 1:02d}-01", "%Y-%m-%d").date()
        return start, end
    parsed_start = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None
    parsed_end = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None
    return parsed_start, parsed_end

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
        description=f"Receipt from {vendor}",
        source_type="manual",
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
            "pinned_queries": (
                db.query(SavedQuery)
                .filter(SavedQuery.owner_email == user_email, SavedQuery.is_pinned.is_(True))
                .order_by(SavedQuery.id.desc())
                .all()
            ),
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
            "trend": {"labels": ["No Data"], "data": [1]},
            "base_currency": settings.BASE_CURRENCY,
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