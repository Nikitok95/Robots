"""FRED (St. Louis Fed). Docs: https://fred.stlouisfed.org/docs/api/fred/series_observations.html"""
from __future__ import annotations

from datetime import date

from .base import Obs, SourceAdapter, SourceError, http, to_float

URL = "https://api.stlouisfed.org/fred/series/observations"


class FredAdapter(SourceAdapter):
    name = "fred"
    label = "FRED"
    key_setting = "fred_api_key"
    homepage = "https://fred.stlouisfed.org"

    def fetch(self, params: dict, since: date | None) -> list[Obs]:
        q = {
            "series_id": params["series_id"],
            "api_key": self.require_key(),
            "file_type": "json",
        }
        if since:
            q["observation_start"] = since.isoformat()
        data = http.get(URL, params=q).json()
        if "observations" not in data:
            raise SourceError(f"FRED: unexpected response {str(data)[:200]}")
        out = []
        for o in data["observations"]:
            v = to_float(o.get("value"))
            if v is not None:
                out.append(Obs(o["date"], v))
        return out
