"""World Bank Indicators API v2 (annual, no key). https://datahelpdesk.worldbank.org"""
from __future__ import annotations

from datetime import date

from .base import Obs, SourceAdapter, SourceError, http, to_float

URL = "https://api.worldbank.org/v2/country/{code}/indicator/{indicator}"


class WorldBankAdapter(SourceAdapter):
    name = "worldbank"
    label = "World Bank"
    homepage = "https://data.worldbank.org"

    def source_label(self, params: dict) -> str:
        return f"{self.label} · {params['indicator']}"

    def fetch(self, params: dict, since: date | None) -> list[Obs]:
        y = date.today().year
        data = http.get(URL.format(code=params["code"], indicator=params["indicator"]),
                        params={"format": "json", "per_page": 100, "date": f"{y - 15}:{y}"}).json()
        if not isinstance(data, list) or len(data) < 2 or data[1] is None:
            msg = data[0].get("message") if isinstance(data, list) and data and isinstance(data[0], dict) else data
            raise SourceError(f"World Bank: {str(msg)[:200]}")
        return sorted((Obs(f"{r['date']}-01-01", v) for r in data[1]
                       if (v := to_float(r.get("value"))) is not None), key=lambda o: o.date)
