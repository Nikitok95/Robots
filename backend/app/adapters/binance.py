"""Binance public market data (no key).
spot_close: /api/v3/klines 1d (fallback host data-api.binance.vision)
funding:    /fapi/v1/fundingRate -> daily mean of 8h funding, in %
oi:         /futures/data/openInterestHist period=1d (only last 30 days available,
            history accumulates in our DB), in BTC.
Note: Binance returns HTTP 451 for US IPs."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from .base import Obs, SourceAdapter, SourceError, http

SPOT_HOSTS = ["https://api.binance.com", "https://data-api.binance.vision"]
FAPI = "https://fapi.binance.com"


def _ms(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp() * 1000)


def _day(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date().isoformat()


class BinanceAdapter(SourceAdapter):
    name = "binance"
    label = "Binance"
    homepage = "https://developers.binance.com"

    def source_label(self, params: dict) -> str:
        return f"{self.label} · {params['symbol']} {params['metric']}"

    def fetch(self, params: dict, since: date | None) -> list[Obs]:
        m = params["metric"]
        start = since or (date.today() - timedelta(days=365 * 3))
        if m == "spot_close":
            return self._spot(params["symbol"], start)
        if m == "funding":
            return self._funding(params["symbol"], start)
        if m == "oi":
            return self._oi(params["symbol"])
        raise SourceError(f"Binance: неизвестная метрика {m}")

    def _spot(self, symbol: str, start: date) -> list[Obs]:
        last_err: Exception | None = None
        for host in SPOT_HOSTS:
            try:
                out: dict[str, float] = {}
                t = _ms(start)
                for _ in range(10):
                    rows = http.get(f"{host}/api/v3/klines", params={
                        "symbol": symbol, "interval": "1d", "startTime": t, "limit": 1000}).json()
                    if not isinstance(rows, list):
                        raise SourceError(f"Binance: {str(rows)[:200]}")
                    for k in rows:
                        out[_day(k[0])] = float(k[4])
                    if len(rows) < 1000:
                        break
                    t = rows[-1][0] + 86400000
                return [Obs(d, v) for d, v in sorted(out.items())]
            except SourceError as e:
                last_err = e
        raise SourceError(str(last_err))

    def _funding(self, symbol: str, start: date) -> list[Obs]:
        acc: dict[str, list[float]] = defaultdict(list)
        t = _ms(start)
        for _ in range(20):
            rows = http.get(f"{FAPI}/fapi/v1/fundingRate", params={
                "symbol": symbol, "startTime": t, "limit": 1000}).json()
            if not isinstance(rows, list):
                raise SourceError(f"Binance funding: {str(rows)[:200]}")
            for r in rows:
                acc[_day(int(r["fundingTime"]))].append(float(r["fundingRate"]) * 100)
            if len(rows) < 1000:
                break
            t = int(rows[-1]["fundingTime"]) + 1
        return [Obs(d, sum(v) / len(v)) for d, v in sorted(acc.items())]

    def _oi(self, symbol: str) -> list[Obs]:
        rows = http.get(f"{FAPI}/futures/data/openInterestHist", params={
            "symbol": symbol, "period": "1d", "limit": 30}).json()
        if not isinstance(rows, list):
            raise SourceError(f"Binance OI: {str(rows)[:200]}")
        return [Obs(_day(int(r["timestamp"])), float(r["sumOpenInterest"])) for r in rows]
