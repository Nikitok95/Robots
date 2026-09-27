"""BIS SDMX REST API v1 (no key). https://stats.bis.org/api-doc/v1/
WS_CBPOL  central bank policy rates, key FREQ.REF_AREA (e.g. D.US, M.XM)
WS_LONG_CPI consumer prices, key FREQ.REF_AREA.UNIT_MEASURE (771 = YoY %)
WS_SPP    residential property prices, key FREQ.REF_AREA.VALUE.UNIT_MEASURE"""
from __future__ import annotations

import csv
import io
from datetime import date, timedelta

from .base import Obs, SourceAdapter, SourceError, http, to_float
from .sdmx_common import norm_period

URL = "https://stats.bis.org/api/v1/data/{flow}/{key}/all"
CSV_ACCEPT = "application/vnd.sdmx.data+csv;version=1.0.0"


def parse_csv(text: str) -> list[Obs]:
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or "OBS_VALUE" not in reader.fieldnames:
        raise SourceError(f"BIS: неожиданный CSV {text[:200]}")
    out: dict[str, float] = {}
    for r in reader:
        d, v = norm_period(r.get("TIME_PERIOD", "")), to_float(r.get("OBS_VALUE"))
        if d and v is not None:
            out[d] = v
    return [Obs(d, v) for d, v in sorted(out.items())]


class BisAdapter(SourceAdapter):
    name = "bis"
    label = "BIS"
    homepage = "https://data.bis.org"

    def source_label(self, params: dict) -> str:
        return f"{self.label} · {params['flow']} {params['key']}"

    def fetch(self, params: dict, since: date | None) -> list[Obs]:
        start = since or (date.today() - timedelta(days=365 * 12))
        freq = params["key"].split(".")[0]
        sp = start.isoformat() if freq == "D" else (start.strftime("%Y-%m") if freq == "M" else str(start.year))
        r = http.get(URL.format(flow=params["flow"], key=params["key"]),
                     params={"startPeriod": sp, "detail": "dataonly"},
                     headers={"Accept": CSV_ACCEPT})
        if not r.text.strip():
            return []
        return parse_csv(r.text)
