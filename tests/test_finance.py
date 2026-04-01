from datetime import date

from app.services.finance import FXService


def test_convert_to_base_same_currency_short_circuits() -> None:
    service = FXService()
    service.base_currency = "EUR"
    converted, rate = service.convert_to_base(12.5, "EUR", date(2026, 1, 1))
    assert converted == 12.5
    assert rate == 1.0


def test_convert_to_base_uses_fetched_rate(monkeypatch) -> None:
    service = FXService()
    service.base_currency = "EUR"

    def fake_fetch_rate(*args, **kwargs):
        return 0.8

    monkeypatch.setattr(service, "_fetch_rate", fake_fetch_rate)
    converted, rate = service.convert_to_base(10, "USD", date(2026, 1, 1))
    assert converted == 8.0
    assert rate == 0.8


def test_convert_to_base_falls_back_on_missing_rate(monkeypatch) -> None:
    service = FXService()
    service.base_currency = "EUR"

    def fake_fetch_rate(*args, **kwargs):
        return None

    monkeypatch.setattr(service, "_fetch_rate", fake_fetch_rate)
    converted, rate = service.convert_to_base(10, "USD", date(2026, 1, 1))
    assert converted == 10.0
    assert rate == 1.0
