"""Bank of Japan Time-Series Data Search API (launched Feb 2026, no key).
Manual: https://www.stat-search.boj.or.jp/info/api_manual_en.pdf
Example: /api/v1/getDataCode?format=json&lang=en&db=FM01&code=STRDCLUCON&startDate=202501
FM01/STRDCLUCON = uncollateralized overnight call rate (average), daily — the
BOJ's operating target."""
from __future__ import annotations

from datetime import date, timedelta

from .base import Obs, SourceAdapter, SourceError, http, to_float

URL = "https://www.stat-search.boj.or.jp/api/v1/getDataCode"


def _norm_date(s: str) -> str | None:
    s = str(s).strip().replace("/", "").replace("-", "")
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    if len(s) == 6 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-01"
    return None


def parse_response(data: dict, code: str) -> list[Obs]:
    """The API returns RESULTSET[] with per-series VALUES {SURVEY_DATES:[], VALUES:[]}."""
    rs = data.get("RESULTSET") or data.get("resultset")
    if rs is None:
        raise SourceError(f"BOJ: неожиданный ответ {str(data)[:200]}")
    out: list[Obs] = []
    for s in rs:  # one code requested -> every result belongs to it
        vals = s.get("VALUES") or {}
        dates = vals.get("SURVEY_DATES") or []
        values = vals.get("VALUES") or []
        for d, v in zip(dates, values):
            nd, fv = _norm_date(d), to_float(v)
            if nd and fv is not None:
                out.append(Obs(nd, fv))
    return out


class BojAdapter(SourceAdapter):
    name = "boj"
    label = "Bank of Japan"
    homepage = "https://www.stat-search.boj.or.jp/index_en.html"

    def fetch(self, params: dict, since: date | None) -> list[Obs]:
        start = since or (date.today() - timedelta(days=365 * 6))
        q = {"format": "json", "lang": "en", "db": params["db"], "code": params["code"],
             "startDate": start.strftime("%Y%m")}
        out: list[Obs] = []
        pos = None
        for _ in range(20):
            if pos:
                q["startPosition"] = pos
            data = http.get(URL, params=q).json()
            status = str(data.get("STATUS", "200"))
            if status not in ("200", "OK"):
                raise SourceError(f"BOJ: {data.get('MESSAGE', status)}")
            out += parse_response(data, params["code"])
            pos = data.get("NEXTPOSITION")
            if not pos:
                break
        return sorted({o.date: o for o in out}.values(), key=lambda o: o.date)
