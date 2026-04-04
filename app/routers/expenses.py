from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.parsing import parse_filter_dates, parse_iso_date
from app.core.security import require_user_email
from app.db.session import get_db
from app.models.expense import Expense
from app.models.saved_query import SavedQuery
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
    parsed_date = parse_iso_date(date) or datetime.now().date()
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
async def my_expenses(
    request: Request,
    month: str | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    user_email = require_user_email(request)
    query = db.query(Expense).filter(Expense.owner_email == user_email)
    filter_start, filter_end, month_mode = parse_filter_dates(month=month, start_date=start_date, end_date=end_date)
    if filter_start:
        query = query.filter(Expense.date >= filter_start)
    if filter_end:
        # End date is inclusive for explicit range; exclusive when derived from month.
        if month_mode:
            query = query.filter(Expense.date < filter_end)
        else:
            query = query.filter(Expense.date <= filter_end)
    expenses = query.order_by(Expense.date.desc()).all()
    return templates.TemplateResponse(
        request=request,
        name="expenses.html",
        context={
            "request": request,
            "expenses": expenses,
            "base_currency": settings.BASE_CURRENCY,
            "pinned_queries": (
                db.query(SavedQuery)
                .filter(SavedQuery.owner_email == user_email, SavedQuery.is_pinned.is_(True))
                .order_by(SavedQuery.id.desc())
                .all()
            ),
            "filter_month": month or "",
            "filter_start_date": start_date or "",
            "filter_end_date": end_date or "",
            "app_version": settings.PROJECT_VERSION,
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
async def get_chart_data(
    request: Request,
    month: str | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    user_email = require_user_email(request)
    filter_start, filter_end, month_mode = parse_filter_dates(month=month, start_date=start_date, end_date=end_date)

    base_filter = [Expense.owner_email == user_email]
    if filter_start:
        base_filter.append(Expense.date >= filter_start)
    if filter_end:
        if month_mode:
            base_filter.append(Expense.date < filter_end)
        else:
            base_filter.append(Expense.date <= filter_end)
    # 1. Category Breakdown (Doughnut)
    cat_data = (
        db.query(Expense.category, func.sum(Expense.base_currency_amount))
        .filter(*base_filter)
        .group_by(Expense.category)
        .all()
    )
    
    # 2. Top 5 Vendors (Bar)
    vendor_data = (
        db.query(Expense.vendor, func.sum(Expense.base_currency_amount))
        .filter(*base_filter)
        .group_by(Expense.vendor)
        .order_by(func.sum(Expense.base_currency_amount).desc())
        .limit(5)
        .all()
    )
    
    # 3. Monthly Trend (Line)
    trend_rows = (
        db.query(Expense.date, Expense.base_currency_amount)
        .filter(*base_filter)
        .order_by(Expense.date.asc())
        .all()
    )
    trend_map: dict[str, float] = {}
    for tx_date, tx_amount in trend_rows:
        key = tx_date.strftime("%Y-%m")
        trend_map[key] = trend_map.get(key, 0.0) + float(tx_amount or 0.0)
    trend_data = list(trend_map.items())[-12:]

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