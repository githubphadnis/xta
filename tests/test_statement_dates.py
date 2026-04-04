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
