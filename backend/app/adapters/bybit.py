"""Bybit v5 public market data (no key). Fallback for funding / OI.
funding: /v5/market/funding/history -> daily mean, in %
oi:      /v5/market/open-interest intervalTime=1d, in BTC (linear contracts)."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from .base import Obs, SourceAdapter, SourceError, http

BASE = "https://api.bybit.com"


def _day(ms) -> str:
    return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).date().isoformat()


class BybitAdapter(SourceAdapter):
    name = "bybit"
    label = "Bybit"
    homepage = "https://bybit-exchange.github.io/docs/v5/intro"

    def source_label(self, params: dict) -> str:
        return f"{self.label} · {params['symbol']} {params['metric']}"

    def _get(self, path: str, q: dict) -> dict:
        data = http.get(BASE + path, params=q, cache=False).json()
        if data.get("retCode") != 0:
            raise SourceError(f"Bybit: {data.get('retMsg')}")
        return data["result"]

    def fetch(self, params: dict, since: date | None) -> list[Obs]:
        start = since or (date.today() - timedelta(days=365 * 2))
        start_ms = int(datetime(start.year, start.month, start.day, tzinfo=timezone.utc).timestamp() * 1000)
        sym = params["symbol"]
        if params["metric"] == "funding":
            acc: dict[str, list[float]] = defaultdict(list)
            end_ms = None
            for _ in range(30):
                q = {"category": "linear", "symbol": sym, "limit": 200}
                if end_ms:
                    q["endTime"] = end_ms
                rows = self._get("/v5/market/funding/history", q)["list"]
                if not rows:
                    break
                for r in rows:
                    acc[_day(r["fundingRateTimestamp"])].append(float(r["fundingRate"]) * 100)
                oldest = min(int(r["fundingRateTimestamp"]) for r in rows)
                if oldest <= start_ms or len(rows) < 200:
                    break
                end_ms = oldest - 1
            return [Obs(d, sum(v) / len(v)) for d, v in sorted(acc.items()) if d >= start.isoformat()]
        if params["metric"] == "oi":
            out: dict[str, float] = {}
            cursor = None
            for _ in range(10):
                q = {"category": "linear", "symbol": sym, "intervalTime": "1d", "limit": 200}
                if cursor:
                    q["cursor"] = cursor
                res = self._get("/v5/market/open-interest", q)
                for r in res["list"]:
                    out[_day(r["timestamp"])] = float(r["openInterest"])
                cursor = res.get("nextPageCursor")
                if not cursor or not res["list"] or min(int(r["timestamp"]) for r in res["list"]) <= start_ms:
                    break
            return [Obs(d, v) for d, v in sorted(out.items()) if d >= start.isoformat()]
        raise SourceError(f"Bybit: неизвестная метрика {params['metric']}")
