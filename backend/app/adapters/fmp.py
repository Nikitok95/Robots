"""Financial Modeling Prep economic calendar (key FMP_API_KEY; plan-dependent).
Docs: https://site.financialmodelingprep.com/developer/docs"""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone

from ..config import get_settings
from .base import CalendarAdapter, SourceError, http

URL = "https://financialmodelingprep.com/stable/economic-calendar"


class FmpCalendar(CalendarAdapter):
    name = "fmp"
    label = "Financial Modeling Prep"
    key_setting = "fmp_api_key"

    def fetch_events(self, start: date, end: date) -> list[dict]:
        rows = http.get(URL, params={"from": start.isoformat(), "to": end.isoformat(),
                                     "apikey": get_settings().fmp_api_key}, cache=False).json()
        if not isinstance(rows, list):
            raise SourceError(f"FMP: {str(rows)[:200]}")
        out = []
        for r in rows:
            try:
                ts = datetime.fromisoformat(str(r["date"]).replace(" ", "T")).replace(tzinfo=timezone.utc)
            except (KeyError, ValueError):
                continue
            title = r.get("event") or ""
            out.append({
                "id": "fmp" + hashlib.sha1(f"{r.get('country')}|{title}|{ts}".encode()).hexdigest()[:14],
                "currency": (r.get("currency") or "").upper() or None, "country": r.get("country"),
                "ts": ts.isoformat(), "title": title, "impact": r.get("impact"),
                "actual": _s(r.get("actual")), "forecast": _s(r.get("estimate")), "previous": _s(r.get("previous")),
            })
        return out


def _s(v):
    return None if v is None else str(v)
