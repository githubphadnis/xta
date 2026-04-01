import os
from datetime import date, datetime, timedelta
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import text, func, extract

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
def read_root(request: Request, db: Session = Depends(get_db)):
    user_email = require_user_email(request)
    # Get current month and year for filtering
    current_month = datetime.now().month
    current_year = datetime.now().year

    # 1. Calculate Monthly Total
    total_spent = db.query(func.sum(Expense.base_currency_amount)).filter(
        Expense.owner_email == user_email,
        extract('month', Expense.date) == current_month,
        extract('year', Expense.date) == current_year
    ).scalar() or 0.0

    # 2. Count Monthly Receipts
    recent_count = db.query(Expense).filter(
        Expense.owner_email == user_email,
        extract('month', Expense.date) == current_month,
        extract('year', Expense.date) == current_year
    ).count()

    # 3. Rolling 30-day and previous-30-day spend for quick trend context.
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

    # 4. Top category this month for a richer at-a-glance dashboard signal.
    top_category_row = (
        db.query(Expense.category, func.sum(Expense.base_currency_amount).label("amount"))
        .filter(
            Expense.owner_email == user_email,
            extract('month', Expense.date) == current_month,
            extract('year', Expense.date) == current_year,
        )
        .group_by(Expense.category)
        .order_by(func.sum(Expense.base_currency_amount).desc())
        .first()
    )
    top_category_name = top_category_row[0] if top_category_row else "N/A"
    top_category_amount = float(top_category_row[1]) if top_category_row else 0.0

    # 5. Get Recent Activity (Last 5 expenses)
    recent_expenses = (
        db.query(Expense)
        .filter(Expense.owner_email == user_email)
        .order_by(Expense.date.desc(), Expense.id.desc())
        .limit(5)
        .all()
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
            "rolling_30d_spend": f"{rolling_30d_spend:.2f}",
            "spend_delta_pct": f"{spend_delta_pct:.1f}",
            "top_category_name": top_category_name,
            "top_category_amount": f"{top_category_amount:.2f}",
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