from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime

from app.db.session import get_db
from app.models.expense import Expense

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.post("/expenses/confirm")
async def confirm_expense(
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

    new_expense = Expense(
        vendor=vendor,
        amount=amount,
        date=parsed_date,
        currency=currency,
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
    expenses = db.query(Expense).order_by(Expense.date.desc()).all()
    return templates.TemplateResponse("expenses.html", {
        "request": request,
        "expenses": expenses
    })

@router.delete("/expenses/{expense_id}")
async def delete_expense(expense_id: int, db: Session = Depends(get_db)):
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if expense:
        db.delete(expense)
        db.commit()
    return "" 

@router.get("/api/expenses/chart-data")
async def get_chart_data(db: Session = Depends(get_db)):
    # 1. Category Breakdown (Doughnut)
    cat_data = db.query(Expense.category, func.sum(Expense.amount)).group_by(Expense.category).all()
    
    # 2. Top 5 Vendors (Bar)
    vendor_data = db.query(Expense.vendor, func.sum(Expense.amount)).group_by(Expense.vendor).order_by(func.sum(Expense.amount).desc()).limit(5).all()
    
    # 3. Monthly Trend (Line) - PostgreSQL specific grouping
    trend_data = db.query(func.to_char(Expense.date, 'YYYY-MM').label('month'), func.sum(Expense.amount)).group_by('month').order_by('month').limit(12).all()

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
        }
    }