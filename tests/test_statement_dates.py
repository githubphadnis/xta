from datetime import date

from app.core.parsing import normalize_date_string, parse_date_str
from app.services.statement_service import StatementService


def test_normalize_date_prefers_unambiguous_iso() -> None:
    service = StatementService()
    # YYYY-MM-DD should be treated as ISO and preserved.
    parsed = service._normalize_date("2026-12-01")
    assert parsed == "2026-12-01"


def test_normalize_date_handles_dayfirst_fallback() -> None:
    service = StatementService()
    parsed = service._normalize_date("01.12.2026")
    assert parsed == "2026-12-01"


def test_normalize_date_falls_back_to_today_for_invalid() -> None:
    service = StatementService()
    parsed = service._normalize_date("not-a-date")
    # Ensure stable format.
    assert len(parsed) == 10
    assert parsed.count("-") == 2


def test_parse_fallback_unstructured_extracts_amounts() -> None:
    csv_bytes = b"foo,bar,baz\nStore Alpha,,12.50\n,Random text,7\n"
    rows = StatementService.parse_fallback_unstructured(csv_bytes, "sample.csv")
    assert rows
    assert rows[0]["vendor"].startswith("Store")
    assert rows[0]["amount"] == 12.5


def test_parse_transaction_date_day_first_and_iso_are_correct() -> None:
    assert parse_date_str("2026-12-01") == date(2026, 12, 1)
    assert parse_date_str("01.12.2026") == date(2026, 12, 1)
    assert parse_date_str("01/12/2026") == date(2026, 12, 1)
    assert parse_date_str("12/01/2026") == date(2026, 1, 12)
    assert normalize_date_string("20261201") == "2026-12-01"
