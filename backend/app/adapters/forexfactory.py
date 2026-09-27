"""Forex Factory weekly calendar JSON (free, no key). Covers the current week
(next week when published) for AUD CAD CHF CNY EUR GBP JPY NZD USD."""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone

from .base import CalendarAdapter, SourceError, http

URLS = [
    "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
    "https://nfs.faireconomy.media/ff_calendar_nextweek.json",
]


def parse(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        try:
            ts = datetime.fromisoformat(r["date"]).astimezone(timezone.utc)
        except (KeyError, ValueError):
            continue
        ccy = (r.get("country") or "").upper()
        title = r.get("title") or ""
        eid = hashlib.sha1(f"ff|{ccy}|{title}|{ts.date()}".encode()).hexdigest()[:16]
        out.append({
            "id": eid, "currency": ccy, "country": None, "ts": ts.replace(microsecond=0).isoformat(),
            "title": title, "impact": r.get("impact"), "actual": r.get("actual") or None,
            "forecast": r.get("forecast") or None, "previous": r.get("previous") or None,
        })
    return out


class ForexFactoryCalendar(CalendarAdapter):
    name = "forexfactory"
    label = "Forex Factory"

    def fetch_events(self, start: date, end: date) -> list[dict]:
        events: list[dict] = []
        errors = []
        for i, url in enumerate(URLS):
            try:
                rows = http.get(url, cache=False).json()
                if isinstance(rows, list):
                    events += parse(rows)
            except SourceError as e:
                if i == 0:
                    errors.append(str(e))  # next week feed is optional
        if errors and not events:
            raise SourceError(errors[0])
        return events
