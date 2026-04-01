from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import calendar

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


@dataclass
class DateRange:
    start_date: date | None
    end_date: date | None


class QueryService:
    """A constrained natural-language to SQL helper for expense analytics."""

    def __init__(self) -> None:
        self.base_currency = settings.BASE_CURRENCY

    def answer_question(
        self,
        db: Session,
        owner_email: str,
        question: str,
        month: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> QueryResult:
        normalized = (question or "").strip().lower()
        if not normalized:
            raise ValueError("Question cannot be empty.")

        range_filter = self._resolve_date_range(month=month, start_date=start_date, end_date=end_date)
        where_clause, params = self._build_where_clause(owner_email=owner_email, date_range=range_filter)

        if "visit" in normalized and ("store" in normalized or "vendor" in normalized or "merchant" in normalized):
            sql_query = f"""
                SELECT vendor AS label, COUNT(*) AS value
                FROM expenses
                {where_clause}
                GROUP BY vendor
                ORDER BY value DESC
                LIMIT 10
            """
            chart_type = "bar"
            summary = "Most visited stores by number of transactions."
        elif "biggest" in normalized and ("category" in normalized or "spend pot" in normalized):
            sql_query = """
                SELECT category AS label, SUM(base_currency_amount) AS value
                FROM expenses
            """
            sql_query += where_clause + """
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
            """
            sql_query += where_clause + """
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
            """
            sql_query += where_clause + """
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
            """
            sql_query += where_clause + """
                GROUP BY category
                ORDER BY value DESC
                LIMIT 10
            """
            chart_type = "pie"
            summary = f"Category split in {self.base_currency}."

        rows = db.execute(text(sql_query), params).mappings().all()
        labels: list[str] = [str(r["label"]) for r in rows]
        values: list[float] = [float(r["value"]) for r in rows]
        if range_filter.start_date and range_filter.end_date:
            summary += f" Date range: {range_filter.start_date.isoformat()} to {range_filter.end_date.isoformat()}."
        return QueryResult(
            question=question,
            sql_query=" ".join(sql_query.split()),
            chart_type=chart_type,
            labels=labels,
            values=values,
            summary=summary,
        )

    @staticmethod
    def _resolve_date_range(month: str | None, start_date: str | None, end_date: str | None) -> DateRange:
        if month:
            month_str = month.strip()
            year_part, month_part = month_str.split("-", 1)
            year = int(year_part)
            month_number = int(month_part)
            last_day = calendar.monthrange(year, month_number)[1]
            return DateRange(
                start_date=date(year, month_number, 1),
                end_date=date(year, month_number, last_day),
            )

        parsed_start = date.fromisoformat(start_date) if start_date else None
        parsed_end = date.fromisoformat(end_date) if end_date else None
        return DateRange(start_date=parsed_start, end_date=parsed_end)

    @staticmethod
    def _build_where_clause(owner_email: str, date_range: DateRange) -> tuple[str, dict[str, object]]:
        params: dict[str, object] = {"owner_email": owner_email}
        clauses = ["owner_email = :owner_email"]
        if date_range.start_date:
            clauses.append("date >= :start_date")
            params["start_date"] = date_range.start_date
        if date_range.end_date:
            clauses.append("date <= :end_date")
            params["end_date"] = date_range.end_date
        return "WHERE " + " AND ".join(clauses), params


query_service = QueryService()
