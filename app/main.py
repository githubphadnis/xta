import os
from datetime import date, timedelta

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

def _inject_common_template_context(request: Request) -> dict[str, object]:
    return {"request": request, "app_version": settings.PROJECT_VERSION}

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
    month_mode = False
    if month:
        try:
            year_part, month_part = month.split("-", 1)
            year = int(year_part)
            month_num = int(month_part)
            parsed_start = date(year, month_num, 1)
            if month_num == 12:
                parsed_end = date(year + 1, 1, 1)
            else:
                parsed_end = date(year, month_num + 1, 1)
            month_mode = True
        except Exception:
            parsed_start = None
            parsed_end = None
            month_mode = False
    else:
        try:
            parsed_start = date.fromisoformat(start_date) if start_date else None
            parsed_end = date.fromisoformat(end_date) if end_date else None
        except ValueError:
            parsed_start = None
            parsed_end = None

    base_query = db.query(Expense).filter(Expense.owner_email == user_email)
    if parsed_start:
        base_query = base_query.filter(Expense.date >= parsed_start)
    if parsed_end:
        if month_mode:
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
        if month_mode:
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

    monthly_rollup: dict[str, float] = {}
    twelve_month_start = today - timedelta(days=365)
    recent_year_rows = (
        db.query(Expense.date, Expense.base_currency_amount)
        .filter(
            Expense.owner_email == user_email,
            Expense.date >= twelve_month_start,
            Expense.date <= today,
        )
        .all()
    )
    for tx_date, tx_amount in recent_year_rows:
        key = tx_date.strftime("%Y-%m")
        monthly_rollup[key] = monthly_rollup.get(key, 0.0) + float(tx_amount or 0.0)
    spend_12m_total = sum(monthly_rollup.values())
    avg_12m_monthly = (spend_12m_total / len(monthly_rollup)) if monthly_rollup else 0.0
    latest_month_label = max(monthly_rollup.keys()) if monthly_rollup else "N/A"

    # 5) Get Recent Activity (Last 5 expenses) in selected range
    recent_expenses = (
        base_query.order_by(Expense.date.desc(), Expense.id.desc()).limit(5).all()
    )
    monthly_rollup: dict[str, float] = {}
    for tx_date, tx_amount in recent_year_rows:
        key = tx_date.strftime("%Y-%m")
        monthly_rollup[key] = monthly_rollup.get(key, 0.0) + float(tx_amount or 0.0)
    spend_12m_total = sum(monthly_rollup.values())
    avg_12m_monthly = (spend_12m_total / len(monthly_rollup)) if monthly_rollup else 0.0
    latest_month_label = max(monthly_rollup.keys()) if monthly_rollup else "N/A"

    # 5) Get Recent Activity (Last 5 expenses) in selected range
    recent_expenses = (
        base_query.order_by(Expense.date.desc(), Expense.id.desc()).limit(5).all()
    )

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            **_inject_common_template_context(request),
            "app_name": settings.PROJECT_NAME,
            "total_spent": total_spent,
            "total_spent_display": f"{total_spent:.2f}",
            "recent_count": recent_count,
            "recent_expenses": recent_expenses,
            "base_currency": settings.BASE_CURRENCY,
            "avg_spent": avg_spent,
            "avg_spent_display": f"{avg_spent:.2f}",
            "top_category": top_category_name,
            "top_category_name": top_category_name,
            "top_category_amount": top_category_amount,
            "top_category_amount_display": f"{top_category_amount:.2f}",
            "rolling_30d_spend": rolling_30d_spend,
            "rolling_30d_spend_display": f"{rolling_30d_spend:.2f}",
            "spend_delta_pct": f"{spend_delta_pct:.1f}",
            "spend_delta_pct_value": spend_delta_pct,
            "spend_delta_pct_display": f"{spend_delta_pct:.1f}",
            "previous_30d_spend": previous_30d_spend,
            "previous_30d_spend_display": f"{previous_30d_spend:.2f}",
            "spend_12m_total": spend_12m_total,
            "spend_12m_total_display": f"{spend_12m_total:.2f}",
            "avg_12m_monthly": avg_12m_monthly,
            "avg_12m_monthly_display": f"{avg_12m_monthly:.2f}",
            "latest_month_label": latest_month_label,
            "filter_month": month or "",
            "filter_start_date": start_date or "",
            "filter_end_date": end_date or "",
            "app_version": settings.PROJECT_VERSION,
        },
    )

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "online",
            "database": "connected",
            "version": settings.PROJECT_VERSION,
            "base_currency": settings.BASE_CURRENCY,
        }
    except Exception:
        return JSONResponse(
            status_code=503,
            content={
                "status": "offline",
                "database": "disconnected",
                "version": settings.PROJECT_VERSION,
                "base_currency": settings.BASE_CURRENCY,
            },
        )