import os
from datetime import date, datetime, timedelta

from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import require_user_email
from app.db.session import get_db
from app.routers import expenses, insights, upload
from app.models.expense import Expense

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION
)

# Static and Templates
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory="app/templates")

# Include our backend logic
app.include_router(upload.router)
app.include_router(expenses.router)
app.include_router(insights.router)

@app.get("/")
def read_root(
    request: Request,
    month: str | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    user_email = require_user_email(request)
    parsed_start = None
    parsed_end = None
    if month:
        try:
            y, m = month.split("-", 1)
            parsed_start = datetime.strptime(f"{y}-{m}-01", "%Y-%m-%d").date()
            if int(m) == 12:
                parsed_end = datetime.strptime(f"{int(y) + 1}-01-01", "%Y-%m-%d").date()
            else:
                parsed_end = datetime.strptime(f"{y}-{int(m) + 1:02d}-01", "%Y-%m-%d").date()
        except Exception:
            parsed_start = None
            parsed_end = None
    else:
        try:
            parsed_start = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None
            parsed_end = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None
        except ValueError:
            parsed_start = None
            parsed_end = None

    base_query = db.query(Expense).filter(Expense.owner_email == user_email)
    if parsed_start:
        base_query = base_query.filter(Expense.date >= parsed_start)
    if parsed_end:
        if month:
            base_query = base_query.filter(Expense.date < parsed_end)
        else:
            base_query = base_query.filter(Expense.date <= parsed_end)

    # 1) Selected range spend and count
    total_spent = base_query.with_entities(func.sum(Expense.base_currency_amount)).scalar() or 0.0
    recent_count = base_query.count()
    avg_spent = (total_spent / recent_count) if recent_count > 0 else 0.0

    # 2) Rolling 30-day and previous-30-day spend for quick trend context.
    today = date.today()
    rolling_start = today - timedelta(days=30)
    previous_start = rolling_start - timedelta(days=30)
    rolling_30d_spend = (
        db.query(func.sum(Expense.base_currency_amount))
        .filter(
            Expense.owner_email == user_email,
            Expense.date >= rolling_start,
            Expense.date <= today,
        )
        .scalar()
        or 0.0
    )
    previous_30d_spend = (
        db.query(func.sum(Expense.base_currency_amount))
        .filter(
            Expense.owner_email == user_email,
            Expense.date >= previous_start,
            Expense.date < rolling_start,
        )
        .scalar()
        or 0.0
    )
    spend_delta_pct = 0.0
    if previous_30d_spend > 0:
        spend_delta_pct = ((rolling_30d_spend - previous_30d_spend) / previous_30d_spend) * 100.0

    # 3) Top category in selected range
    top_category_row = (
        db.query(Expense.category, func.sum(Expense.base_currency_amount).label("amount"))
        .filter(
            Expense.owner_email == user_email,
        )
    )
    if parsed_start:
        top_category_row = top_category_row.filter(Expense.date >= parsed_start)
    if parsed_end:
        if month:
            top_category_row = top_category_row.filter(Expense.date < parsed_end)
        else:
            top_category_row = top_category_row.filter(Expense.date <= parsed_end)
    top_category_row = (
        top_category_row
        .group_by(Expense.category)
        .order_by(func.sum(Expense.base_currency_amount).desc())
        .first()
    )
    top_category_name = top_category_row[0] if top_category_row else "N/A"
    top_category_amount = float(top_category_row[1]) if top_category_row else 0.0

    # 4) Get Recent Activity (Last 5 expenses) in selected range
    recent_expenses = (
        base_query.order_by(Expense.date.desc(), Expense.id.desc()).limit(5).all()
    )

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "request": request,
            "app_name": settings.PROJECT_NAME,
            "total_spent": f"{total_spent:.2f}",
            "recent_count": recent_count,
            "recent_expenses": recent_expenses,
            "base_currency": settings.BASE_CURRENCY,
            "avg_spent": f"{avg_spent:.2f}",
            "top_category": top_category_name,
            "top_category_amount": f"{top_category_amount:.2f}",
            "rolling_30d_spend": f"{rolling_30d_spend:.2f}",
            "spend_delta_pct": f"{spend_delta_pct:.1f}",
            "spend_delta_pct_value": spend_delta_pct,
            "filter_month": month or "",
            "filter_start_date": start_date or "",
            "filter_end_date": end_date or "",
        },
    )

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "online", "database": "connected"}
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "offline", "database": "disconnected"},
        )