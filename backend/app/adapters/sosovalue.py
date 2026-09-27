"""SoSoValue open API: daily net inflow of US spot BTC ETFs (free key,
header x-soso-api-key). Endpoint URL is configurable via SOSOVALUE_ETF_URL
because SoSoValue has published several API versions. Value in USD millions."""
from __future__ import annotations

from datetime import date, datetime, timezone

from ..config import get_settings
from .base import Obs, SourceAdapter, SourceError, http, to_float

DATE_KEYS = ("date", "day", "tradeDate", "time")
FLOW_KEYS = ("totalNetInflow", "netInflow", "total_net_inflow", "dailyNetInflow")


def _find_rows(obj):
    if isinstance(obj, list) and obj and isinstance(obj[0], dict):
        return obj
    if isinstance(obj, dict):
        for k in ("data", "list", "result", "items"):
            if k in obj:
                r = _find_rows(obj[k])
                if r:
                    return r
    return None


def _norm_date(v) -> str | None:
    if isinstance(v, (int, float)):
        ts = v / 1000 if v > 1e11 else v
        return datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
    s = str(v)[:10]
    try:
        return date.fromisoformat(s).isoformat()
    except ValueError:
        return None


def parse(data) -> list[Obs]:
    if isinstance(data, dict) and data.get("code") not in (None, 0, "0", 200):
        raise SourceError(f"SoSoValue: {data.get('msg') or data.get('message') or data.get('code')}")
    rows = _find_rows(data)
    if not rows:
        raise SourceError(f"SoSoValue: неожиданный ответ {str(data)[:200]}")
    out: dict[str, float] = {}
    for r in rows:
        d = next((_norm_date(r[k]) for k in DATE_KEYS if k in r), None)
        v = next((to_float(r[k]) for k in FLOW_KEYS if k in r), None)
        if d and v is not None:
            out[d] = v / 1e6
    return [Obs(d, v) for d, v in sorted(out.items())]


class SoSoValueAdapter(SourceAdapter):
    name = "sosovalue"
    label = "SoSoValue"
    key_setting = "sosovalue_api_key"
    homepage = "https://sosovalue.com/developer"

    def source_label(self, params: dict) -> str:
        return f"{self.label} · {params['type']}"

    def fetch(self, params: dict, since: date | None) -> list[Obs]:
        key = self.require_key()
        url = get_settings().sosovalue_etf_url
        headers = {"x-soso-api-key": key, "Content-Type": "application/json"}
        r = http.request("POST", url, json={"type": params["type"]}, headers=headers, cache=False)
        out = parse(r.json())
        if since:
            out = [o for o in out if o.date >= since.isoformat()]
        return out
