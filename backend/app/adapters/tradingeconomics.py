"""Trading Economics API (paid; key TRADINGECONOMICS_API_KEY). Optional provider
for PMI / micro data and the economic calendar. Disabled when no key.
Docs: https://docs.tradingeconomics.com"""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from urllib.parse import quote

from .base import CalendarAdapter, Obs, SourceAdapter, SourceError, http, to_float

BASE = "https://api.tradingeconomics.com"
IMPACT = {1: "Low", 2: "Medium", 3: "High"}


class TradingEconomicsAdapter(SourceAdapter):
    name = "tradingeconomics"
    label = "Trading Economics"
    key_setting = "tradingeconomics_api_key"
    homepage = "https://tradingeconomics.com/api"

    def source_label(self, params: dict) -> str:
        return f"{self.label} · {params['indicator']}"

    def fetch(self, params: dict, since: date | None) -> list[Obs]:
        key = self.require_key()
        url = f"{BASE}/historical/country/{quote(params['country'])}/indicator/{quote(params['indicator'])}"
        q = {"c": key, "f": "json"}
        if since:
            url += f"/{since.isoformat()}"
        rows = http.get(url, params=q).json()
        if not isinstance(rows, list):
            raise SourceError(f"TE: {str(rows)[:200]}")
        return sorted((Obs(str(r["DateTime"])[:10], v) for r in rows
                       if (v := to_float(r.get("Value"))) is not None), key=lambda o: o.date)


class TradingEconomicsCalendar(CalendarAdapter):
    name = "tradingeconomics"
    label = "Trading Economics"
    key_setting = "tradingeconomics_api_key"

    def fetch_events(self, start: date, end: date) -> list[dict]:
        from ..config import get_settings
        key = get_settings().tradingeconomics_api_key
        rows = http.get(f"{BASE}/calendar/country/All/{start.isoformat()}/{end.isoformat()}",
                        params={"c": key, "f": "json"}, cache=False).json()
        if not isinstance(rows, list):
            raise SourceError(f"TE calendar: {str(rows)[:200]}")
        out = []
        for r in rows:
            try:
                ts = datetime.fromisoformat(str(r["Date"])).replace(tzinfo=timezone.utc)
            except (KeyError, ValueError):
                continue
            out.append({
                "id": "te" + str(r.get("CalendarId") or hashlib.sha1(str(r).encode()).hexdigest()[:14]),
                "currency": (r.get("Currency") or "").upper() or None, "country": r.get("Country"),
                "ts": ts.isoformat(), "title": r.get("Event") or r.get("Category") or "",
                "impact": IMPACT.get(r.get("Importance")), "actual": r.get("Actual") or None,
                "forecast": r.get("Forecast") or r.get("TEForecast") or None, "previous": r.get("Previous") or None,
            })
        return out
