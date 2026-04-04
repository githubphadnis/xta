from __future__ import annotations

import re
from datetime import date, datetime

import pandas as pd


_CURRENCY_ALIASES = {
    "$": "USD",
    "usd": "USD",
    "us dollar": "USD",
    "€": "EUR",
    "eur": "EUR",
    "euro": "EUR",
    "£": "GBP",
    "gbp": "GBP",
    "pound": "GBP",
    "₹": "INR",
    "inr": "INR",
    "rupee": "INR",
}


def normalize_currency_code(raw_currency: object, default_currency: str) -> str:
    """
    Normalize symbols or free-form currency labels to ISO-4217 code.
    Falls back to the provided default for unknown values.
    """
    default = (default_currency or "EUR").upper()
    text = str(raw_currency or "").strip()
    if not text:
        return default

    alias = _CURRENCY_ALIASES.get(text.lower())
    if alias:
        return alias

    compact = re.sub(r"[^A-Za-z]", "", text).upper()
    if len(compact) == 3 and compact.isalpha():
        return compact
    return default


def normalize_date_string(raw_date: object) -> str:
    """
    Normalize assorted date formats into YYYY-MM-DD.
    - preserves strict ISO
    - supports common day-first patterns used in EU exports
    - supports Excel serial dates
    - falls back to today's date if parsing fails
    """
    if isinstance(raw_date, datetime):
        return raw_date.date().isoformat()
    if isinstance(raw_date, date):
        return raw_date.isoformat()

    text = str(raw_date or "").strip()
    if not text or text.lower() in {"nan", "none", "nat"}:
        return datetime.now().date().isoformat()

    # Keep strict ISO stable.
    try:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except ValueError:
        pass

    # Common explicit formats (including OCR outputs).
    explicit_formats = (
        "%d.%m.%Y",
        "%d.%m.%y",
        "%d/%m/%Y",
        "%d/%m/%y",
        "%m/%d/%Y",
        "%m/%d/%y",
        "%d-%m-%Y",
        "%d-%m-%y",
        "%Y/%m/%d",
    )
    for fmt in explicit_formats:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue

    # Compact YYYYMMDD format (e.g. "20261201").
    if re.fullmatch(r"\d{8}", text):
        try:
            return datetime.strptime(text, "%Y%m%d").date().isoformat()
        except ValueError:
            pass

    # Excel serial date fallback (e.g. "45432").
    if re.fullmatch(r"\d{4,6}", text):
        try:
            serial_value = float(text)
            parsed_serial = pd.to_datetime(serial_value, unit="D", origin="1899-12-30", errors="coerce")
            if pd.notna(parsed_serial):
                return parsed_serial.date().isoformat()
        except Exception:
            pass

    # Flexible parser fallback.
    for dayfirst in (True, False):
        parsed = pd.to_datetime(text, dayfirst=dayfirst, errors="coerce")
        if pd.notna(parsed):
            return parsed.date().isoformat()

    return datetime.now().date().isoformat()


def parse_date_or_today(raw_date: object) -> date:
    return datetime.strptime(normalize_date_string(raw_date), "%Y-%m-%d").date()


def parse_iso_date(raw_date: object) -> date | None:
    """
    Parse a date into a `date` object.
    Returns None if parsing fails.
    """
    normalized = normalize_date_string(raw_date)
    try:
        return datetime.strptime(normalized, "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_transaction_date(raw_date: object) -> str:
    """Compatibility alias used by ingestion code/tests."""
    return normalize_date_string(raw_date)


def parse_date_str(raw_date: object) -> date:
    """Parse a date-like string/object into `date`."""
    parsed = parse_iso_date(raw_date)
    if parsed is None:
        return datetime.now().date()
    return parsed


def parse_filter_dates(
    month: str | None,
    start_date: str | None,
    end_date: str | None,
) -> tuple[date | None, date | None, bool]:
    """
    Resolve dashboard/expenses date filters.
    Returns: (start, end, month_mode)
      - month_mode=True means end is exclusive (first day of next month)
      - month_mode=False means explicit date range, end should be inclusive
    """
    month_value = (month or "").strip()
    if month_value:
        try:
            year_part, month_part = month_value.split("-", 1)
            year = int(year_part)
            month_num = int(month_part)
            start = date(year, month_num, 1)
            if month_num == 12:
                end = date(year + 1, 1, 1)
            else:
                end = date(year, month_num + 1, 1)
            return start, end, True
        except Exception:
            return None, None, False

    parsed_start = parse_iso_date(start_date) if start_date else None
    parsed_end = parse_iso_date(end_date) if end_date else None
    return parsed_start, parsed_end, False
