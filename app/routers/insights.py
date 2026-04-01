from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.security import require_user_email
from app.db.session import get_db
from app.models.saved_query import SavedQuery
from app.services.query_service import query_service

router = APIRouter(prefix="/api/insights", tags=["insights"])


@router.post("/ask")
async def ask_question(
    request: Request,
    question: str = Form(...),
    month: str = Form(default=""),
    start_date: str = Form(default=""),
    end_date: str = Form(default=""),
    db: Session = Depends(get_db),
):
    user_email = require_user_email(request)
    result = query_service.answer_question(
        db=db,
        owner_email=user_email,
        question=question,
        month=month or None,
        start_date=start_date or None,
        end_date=end_date or None,
    )
    return {
        "question": result.question,
        "summary": result.summary,
        "sql": result.sql_query,
        "chart": {
            "type": result.chart_type,
            "labels": result.labels,
            "values": result.values,
        },
    }


@router.post("/save")
async def save_question(
    request: Request,
    name: str = Form(...),
    question: str = Form(...),
    sql_query: str = Form(...),
    chart_type: str = Form("bar"),
    db: Session = Depends(get_db),
):
    user_email = require_user_email(request)
    saved = SavedQuery(
        owner_email=user_email,
        name=name.strip() or "Saved query",
        question=question.strip(),
        sql_query=sql_query.strip(),
        chart_type=chart_type.strip() or "bar",
        is_pinned=False,
    )
    db.add(saved)
    db.commit()
    db.refresh(saved)
    return {"id": saved.id, "status": "saved"}


@router.post("/{saved_query_id}/pin")
async def pin_saved_query(saved_query_id: int, request: Request, db: Session = Depends(get_db)):
    user_email = require_user_email(request)
    saved = (
        db.query(SavedQuery)
        .filter(SavedQuery.id == saved_query_id, SavedQuery.owner_email == user_email)
        .first()
    )
    if not saved:
        raise HTTPException(status_code=404, detail="Saved query not found")
    saved.is_pinned = True
    db.commit()
    return {"id": saved.id, "status": "pinned"}


@router.get("/saved")
async def list_saved_queries(request: Request, db: Session = Depends(get_db)):
    user_email = require_user_email(request)
    rows = (
        db.query(SavedQuery)
        .filter(SavedQuery.owner_email == user_email)
        .order_by(SavedQuery.is_pinned.desc(), SavedQuery.id.desc())
        .all()
    )
    return [
        {
            "id": row.id,
            "name": row.name,
            "question": row.question,
            "sql": row.sql_query,
            "chart_type": row.chart_type,
            "is_pinned": row.is_pinned,
        }
        for row in rows
    ]
