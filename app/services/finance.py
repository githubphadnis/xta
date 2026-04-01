from __future__ import annotations

from datetime import date

import httpx

from app.core.config import settings


class FXService:
    """Converts transaction amounts into a configured base currency."""

    def __init__(self) -> None:
        self.base_currency = settings.BASE_CURRENCY
        self.fx_api_url = settings.FX_API_URL.rstrip("/")

    def convert_to_base(
        self,
        amount: float,
        from_currency: str,
        tx_date: date | None = None,
    ) -> tuple[float, float]:
        """
        Returns: (base_currency_amount, rate_used).
        Falls back to the original amount if rate lookup fails.
        """
        normalized_from = (from_currency or self.base_currency).upper()
        if normalized_from == self.base_currency:
            return float(amount), 1.0

        rate = self._fetch_rate(
            from_currency=normalized_from,
            to_currency=self.base_currency,
            tx_date=tx_date,
        )
        if rate is None or rate <= 0:
            return float(amount), 1.0
        return float(amount) * rate, float(rate)

    def _fetch_rate(self, from_currency: str, to_currency: str, tx_date: date | None) -> float | None:
        # Historical rate path (Frankfurter supports date snapshots).
        if tx_date:
            historical_url = f"{self.fx_api_url}/{tx_date.isoformat()}"
            rate = self._fetch_from_frankfurter(historical_url, from_currency, to_currency)
            if rate is not None:
                return rate

        # Fallback to latest rate on the configured provider.
        latest_url = f"{self.fx_api_url}/latest"
        rate = self._fetch_from_frankfurter(latest_url, from_currency, to_currency)
        if rate is not None:
            return rate

        # Secondary fallback to open.er-api.com (latest only).
        return self._fetch_from_open_er_api(from_currency, to_currency)

    @staticmethod
    def _fetch_from_frankfurter(url: str, from_currency: str, to_currency: str) -> float | None:
        try:
            response = httpx.get(
                url,
                params={"from": from_currency, "to": to_currency},
                timeout=8.0,
            )
            response.raise_for_status()
            payload = response.json()
            rates = payload.get("rates", {})
            value = rates.get(to_currency)
            if value is None:
                return None
            return float(value)
        except Exception:
            return None

    @staticmethod
    def _fetch_from_open_er_api(from_currency: str, to_currency: str) -> float | None:
        try:
            response = httpx.get(
                f"https://open.er-api.com/v6/latest/{from_currency}",
                timeout=8.0,
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("result") != "success":
                return None
            rates = payload.get("rates", {})
            value = rates.get(to_currency)
            if value is None:
                return None
            return float(value)
        except Exception:
            return None


fx_service = FXService()
