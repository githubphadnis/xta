from datetime import date

from app.core.parsing import parse_date_str


def test_parse_date_str_accepts_iso() -> None:
    parsed = parse_date_str("2026-12-01")
    assert parsed == date(2026, 12, 1)


def test_parse_date_str_accepts_month_compact() -> None:
    parsed = parse_date_str("20261201")
    assert parsed == date(2026, 12, 1)


def test_parse_date_str_interprets_slash_as_day_first() -> None:
    parsed = parse_date_str("01/12/2026")
    assert parsed == date(2026, 12, 1)


def test_parse_date_str_interprets_dash_as_month_first_when_ambiguous() -> None:
    parsed = parse_date_str("12-01-2026")
    assert parsed == date(2026, 1, 12)
