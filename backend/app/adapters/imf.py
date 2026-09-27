"""IMF DataMapper API (WEO, Fiscal Monitor; annual incl. projections, no key).
https://www.imf.org/external/datamapper/api/help"""
from __future__ import annotations

from datetime import date

from .base import Obs, SourceAdapter, SourceError, http, to_float

URL = "https://www.imf.org/external/datamapper/api/v1/{indicator}/{code}"


class ImfAdapter(SourceAdapter):
    name = "imf"
    label = "IMF DataMapper"
    homepage = "https://www.imf.org/external/datamapper"

    def source_label(self, params: dict) -> str:
        return f"{self.label} · {params['indicator']}"

    def fetch(self, params: dict, since: date | None) -> list[Obs]:
        ind, code = params["indicator"], params["code"]
        data = http.get(URL.format(indicator=ind, code=code)).json()
        series = ((data.get("values") or {}).get(ind) or {}).get(code)
        if series is None:
            raise SourceError(f"IMF: нет данных {ind}/{code}")
        out = [Obs(f"{y}-01-01", v) for y, raw in sorted(series.items())
               if (v := to_float(raw)) is not None]
        if since:
            out = [o for o in out if o.date >= f"{since.year - 1}-01-01"]
        return out
