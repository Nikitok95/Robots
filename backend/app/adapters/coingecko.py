"""CoinGecko. Keyless public API gives up to 365 days of daily history;
an optional free Demo key (COINGECKO_API_KEY) raises rate limits."""
from __future__ import annotations

from datetime import date, datetime, timezone

from ..config import get_settings
from .base import Obs, SourceAdapter, SourceError, http

URL = "https://api.coingecko.com/api/v3/coins/{coin}/market_chart"


class CoinGeckoAdapter(SourceAdapter):
    name = "coingecko"
    label = "CoinGecko"
    homepage = "https://www.coingecko.com/en/api"

    def source_label(self, params: dict) -> str:
        return f"{self.label} · {params['coin']}"

    def fetch(self, params: dict, since: date | None) -> list[Obs]:
        days = 365
        if since:
            days = max(2, min(365, (date.today() - since).days + 2))
        headers = {}
        key = get_settings().coingecko_api_key
        if key:
            headers["x-cg-demo-api-key"] = key
        data = http.get(URL.format(coin=params["coin"]),
                        params={"vs_currency": "usd", "days": days, "interval": "daily"},
                        headers=headers).json()
        if "prices" not in data:
            raise SourceError(f"CoinGecko: {str(data)[:200]}")
        out: dict[str, float] = {}
        for ts, price in data["prices"]:
            d = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).date().isoformat()
            out[d] = float(price)  # last point of the day wins (today = live price)
        return [Obs(d, v) for d, v in sorted(out.items())]
