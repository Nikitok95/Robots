"""Frankfurter (ECB reference rates, no key). Value = units of currency per 1 USD.
Covers all currencies in config/countries.yaml (AUD..ZAR incl. TRY, INR, KRW)."""
from __future__ import annotations

from datetime import date, timedelta

from .base import Obs, SourceAdapter, SourceError, http

BASE = "https://api.frankfurter.app"


class FrankfurterAdapter(SourceAdapter):
    name = "frankfurter"
    label = "ECB via Frankfurter"
    homepage = "https://frankfurter.dev"

    def source_label(self, params: dict) -> str:
        return f"{self.label} · USD/{params['currency']}"

    def fetch(self, params: dict, since: date | None) -> list[Obs]:
        start = since or (date.today() - timedelta(days=365 * 6))
        # one request for all currencies: identical URL -> shared by the in-memory cache
        data = http.get(f"{BASE}/{start.isoformat()}..", params={"from": "USD"}).json()
        rates = data.get("rates")
        if not isinstance(rates, dict):
            raise SourceError(f"Frankfurter: {str(data)[:200]}")
        ccy = params["currency"]
        return [Obs(d, float(r[ccy])) for d, r in sorted(rates.items()) if ccy in r]
