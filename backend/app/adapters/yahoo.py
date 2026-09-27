"""Yahoo Finance chart API (unofficial, no key). Used for USD/JPY, DXY, MOVE,
Brent, fed funds futures (ZQ). Values labelled "Yahoo Finance (неофиц.)"."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from .base import Obs, SourceAdapter, SourceError, http

URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"


class YahooAdapter(SourceAdapter):
    name = "yahoo"
    label = "Yahoo Finance (неофиц.)"
    homepage = "https://finance.yahoo.com"

    def fetch(self, params: dict, since: date | None) -> list[Obs]:
        symbol = params["symbol"]
        start = since or (date.today() - timedelta(days=365 * 6))
        p1 = int(datetime(start.year, start.month, start.day, tzinfo=timezone.utc).timestamp())
        p2 = int(datetime.now(timezone.utc).timestamp()) + 86400
        r = http.get(URL.format(symbol=symbol),
                     params={"period1": p1, "period2": p2, "interval": "1d", "events": "history"})
        data = r.json()
        chart = data.get("chart") or {}
        if chart.get("error"):
            raise SourceError(f"Yahoo {symbol}: {chart['error']}")
        res = (chart.get("result") or [None])[0]
        if not res or not res.get("timestamp"):
            raise SourceError(f"Yahoo {symbol}: пустой ответ")
        offset = int(res.get("meta", {}).get("gmtoffset") or 0)
        closes = res["indicators"]["quote"][0].get("close") or []
        out: dict[str, float] = {}
        for ts, c in zip(res["timestamp"], closes):
            if c is None:
                continue
            d = datetime.fromtimestamp(ts + offset, tz=timezone.utc).date().isoformat()
            out[d] = float(c)
        return [Obs(d, v) for d, v in sorted(out.items())]
