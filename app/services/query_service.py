from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings


@dataclass
class QueryResult:
    question: str
    sql_query: str
    chart_type: str
    labels: list[str]
    values: list[float]
    summary: str


class QueryService:
    """A constrained natural-language to SQL helper for expense analytics."""

    def __init__(self) -> None:
        self.base_currency = settings.BASE_CURRENCY

    def answer_question(self, db: Session, owner_email: str, question: str) -> QueryResult:
        normalized = (question or "").strip().lower()
        if not normalized:
            raise ValueError("Question cannot be empty.")

        if "biggest" in normalized and ("category" in normalized or "spend pot" in normalized):
            sql_query = """
                SELECT category AS label, SUM(base_currency_amount) AS value
                FROM expenses
                WHERE owner_email = :owner_email
                GROUP BY category
                ORDER BY value DESC
                LIMIT 10
            """
            chart_type = "bar"
            summary = f"Top spending categories in {self.base_currency}."
        elif "vendor" in normalized or "merchant" in normalized:
            sql_query = """
                SELECT vendor AS label, SUM(base_currency_amount) AS value
                FROM expenses
                WHERE owner_email = :owner_email
                GROUP BY vendor
                ORDER BY value DESC
                LIMIT 10
            """
            chart_type = "bar"
            summary = f"Top vendors by spend in {self.base_currency}."
        elif "month" in normalized or "trend" in normalized:
            sql_query = """
                SELECT to_char(date, 'YYYY-MM') AS label, SUM(base_currency_amount) AS value
                FROM expenses
                WHERE owner_email = :owner_email
                GROUP BY label
                ORDER BY label
                LIMIT 24
            """
            chart_type = "line"
            summary = f"Monthly spending trend in {self.base_currency}."
        else:
            sql_query = """
                SELECT category AS label, SUM(base_currency_amount) AS value
                FROM expenses
                WHERE owner_email = :owner_email
                GROUP BY category
                ORDER BY value DESC
                LIMIT 10
            """
            chart_type = "pie"
            summary = f"Category split in {self.base_currency}."

        rows = db.execute(text(sql_query), {"owner_email": owner_email}).mappings().all()
        labels: list[str] = [str(r["label"]) for r in rows]
        values: list[float] = [float(r["value"]) for r in rows]
        return QueryResult(
            question=question,
            sql_query=" ".join(sql_query.split()),
            chart_type=chart_type,
            labels=labels,
            values=values,
            summary=summary,
        )


query_service = QueryService()
