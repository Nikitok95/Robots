"""Coinbase Exchange public API (no key): daily candles BTC-USD."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from .base import Obs, SourceAdapter, SourceError, http

URL = "https://api.exchange.coinbase.com/products/{product}/candles"


class CoinbaseAdapter(SourceAdapter):
    name = "coinbase"
    label = "Coinbase"
    homepage = "https://docs.cdp.coinbase.com/exchange/reference/exchangerestapi_getproductcandles"

    def source_label(self, params: dict) -> str:
        return f"{self.label} · {params['product']}"

    def fetch(self, params: dict, since: date | None) -> list[Obs]:
        start = since or (date.today() - timedelta(days=365 * 3))
        end = date.today() + timedelta(days=1)
        out: dict[str, float] = {}
        cur = start
        while cur < end:
            chunk_end = min(cur + timedelta(days=299), end)
            rows = http.get(URL.format(product=params["product"]), params={
                "granularity": 86400, "start": cur.isoformat(), "end": chunk_end.isoformat()}).json()
            if not isinstance(rows, list):
                raise SourceError(f"Coinbase: {str(rows)[:200]}")
            for t, _lo, _hi, _op, close, _vol in rows:
                out[datetime.fromtimestamp(t, tz=timezone.utc).date().isoformat()] = float(close)
            cur = chunk_end
        return [Obs(d, v) for d, v in sorted(out.items())]
