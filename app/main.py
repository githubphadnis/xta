#2 - Dirty push trick
import os
from datetime import datetime
from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import text, func, extract

from app.core.config import settings
from app.db.session import get_db, engine, Base
from app.routers import upload, expenses
from app.models.expense import Expense

# Force database to create tables
Base.metadata.create_all(bind=engine)

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

@app.get("/")
def read_root(request: Request, db: Session = Depends(get_db)):
    # Get current month and year for filtering
    current_month = datetime.now().month
    current_year = datetime.now().year

    # 1. Calculate Monthly Total
    total_spent = db.query(func.sum(Expense.amount)).filter(
        extract('month', Expense.date) == current_month,
        extract('year', Expense.date) == current_year
    ).scalar() or 0.0

    # 2. Count Monthly Receipts
    recent_count = db.query(Expense).filter(
        extract('month', Expense.date) == current_month,
        extract('year', Expense.date) == current_year
    ).count()

    # 3. Get Recent Activity (Last 5 expenses)
    recent_expenses = db.query(Expense).order_by(Expense.date.desc(), Expense.id.desc()).limit(5).all()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "app_name": settings.PROJECT_NAME,
        "total_spent": f"{total_spent:.2f}",
        "recent_count": recent_count,
        "recent_expenses": recent_expenses
    })

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "online", "database": "connected"}
    except Exception as e:
        return {"status": "online", "database": f"disconnected: {str(e)}"}