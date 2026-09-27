"""CFTC Commitments of Traders via Socrata (no key).
Dataset gpe5-46if = "TFF - Futures Only" (Traders in Financial Futures).
JPY (CME) contract market code 097741. Net leveraged funds = long - short."""
from __future__ import annotations

from datetime import date, timedelta

from .base import Obs, SourceAdapter, SourceError, http

URL = "https://publicreporting.cftc.gov/resource/{dataset}.json"


class CftcAdapter(SourceAdapter):
    name = "cftc"
    label = "CFTC COT"
    homepage = "https://publicreporting.cftc.gov/Commitments-of-Traders/TFF-Futures-Only/gpe5-46if"

    def source_label(self, params: dict) -> str:
        return f"{self.label} · TFF {params['contract_code']}"

    def fetch(self, params: dict, since: date | None) -> list[Obs]:
        start = since or (date.today() - timedelta(days=365 * 6))
        long_f, short_f = params.get("long_field", "lev_money_positions_long"), params.get(
            "short_field", "lev_money_positions_short")
        q = {
            "$select": f"report_date_as_yyyy_mm_dd,{long_f},{short_f}",
            "$where": f"cftc_contract_market_code='{params['contract_code']}' AND "
                      f"report_date_as_yyyy_mm_dd >= '{start.isoformat()}T00:00:00.000'",
            "$order": "report_date_as_yyyy_mm_dd",
            "$limit": 5000,
        }
        rows = http.get(URL.format(dataset=params.get("dataset", "gpe5-46if")), params=q).json()
        if not isinstance(rows, list):
            raise SourceError(f"CFTC: {str(rows)[:200]}")
        out = []
        for r in rows:
            try:
                out.append(Obs(r["report_date_as_yyyy_mm_dd"][:10], float(r[long_f]) - float(r[short_f])))
            except (KeyError, TypeError, ValueError):
                continue
        return out
