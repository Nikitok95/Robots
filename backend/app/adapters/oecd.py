"""OECD SDMX API (no key). https://sdmx.oecd.org/public/rest/
The key layout is read from the dataflow's data structure, so params only name
dimension values, e.g. {"agency": "OECD.SDD.STES", "flow": "DSD_KEI@DF_KEI",
"dims": {"REF_AREA": "USA", "FREQ": "M", "MEASURE": "PRVM"},
"prefer": [{"TRANSFORMATION": "GY"}, {}]}.
Among returned series the first matching `prefer` filter with the latest data wins."""
from __future__ import annotations

import csv
import io
import threading
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date, timedelta

from .base import Obs, SourceAdapter, SourceError, http, to_float
from .sdmx_common import norm_period

BASE = "https://sdmx.oecd.org/public/rest"
_dims_cache: dict[str, list[str]] = {}
_lock = threading.Lock()


def parse_dimensions(xml_text: str) -> list[str]:
    root = ET.fromstring(xml_text)
    dims = []
    for el in root.iter():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag == "Dimension" and el.get("id"):
            dims.append((int(el.get("position") or len(dims) + 1), el.get("id")))
    if not dims:
        raise SourceError("OECD: не удалось прочитать структуру (нет Dimension)")
    # a DSD may be embedded more than once; keep unique ids in position order
    seen, out = set(), []
    for _, d in sorted(dims):
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def select_series(text: str, prefer: list[dict]) -> list[Obs]:
    reader = csv.DictReader(io.StringIO(text))
    fields = reader.fieldnames or []
    if "OBS_VALUE" not in fields or "TIME_PERIOD" not in fields:
        raise SourceError(f"OECD: неожиданный CSV {text[:200]}")
    dim_cols = [f for f in fields if f not in ("TIME_PERIOD", "OBS_VALUE") and f.isupper()
                and not f.startswith("OBS_") and f not in ("DATAFLOW", "STRUCTURE", "STRUCTURE_ID", "ACTION",
                                                         "UNIT_MULT", "DECIMALS", "BASE_PER", "STRUCTURE_NAME")]
    series: dict[tuple, dict[str, float]] = defaultdict(dict)
    meta: dict[tuple, dict] = {}
    for r in reader:
        k = tuple(r.get(c, "") for c in dim_cols)
        d, v = norm_period(r["TIME_PERIOD"]), to_float(r["OBS_VALUE"])
        if d and v is not None:
            series[k][d] = v
            meta[k] = {c: r.get(c, "") for c in dim_cols}
    if not series:
        return []
    for flt in prefer or [{}]:
        cands = [k for k in series if all(meta[k].get(a) == b for a, b in flt.items())]
        if cands:
            best = max(cands, key=lambda k: (max(series[k]), len(series[k])))
            return [Obs(d, v) for d, v in sorted(series[best].items())]
    seen = {c: sorted({m.get(c, "") for m in meta.values()}) for c in dim_cols}
    raise SourceError(f"OECD: нет серии под фильтр {prefer}; доступно {seen}")


import threading as _threading
import time as _time

# Публичный API OECD пускает ~20 запросов в минуту с адреса и отвечает 429 на
# залпы (проверено 2026-09-28): держим не чаще одного запроса в 3,5 с.
_PACE_SEC = 3.5
_pace_lock = _threading.Lock()
_pace_last = [0.0]


def _pace() -> None:
    with _pace_lock:
        wait = _pace_last[0] + _PACE_SEC - _time.monotonic()
        if wait > 0:
            _time.sleep(wait)
        _pace_last[0] = _time.monotonic()


class OecdAdapter(SourceAdapter):
    name = "oecd"
    label = "OECD"
    homepage = "https://data-explorer.oecd.org"

    def source_label(self, params: dict) -> str:
        d = params["dims"]
        return f"{self.label} · {params['flow'].split('@')[-1]} {d.get('MEASURE', '')}".strip()

    def dimensions(self, agency: str, flow: str) -> list[str]:
        ck = f"{agency}/{flow}"
        with _lock:
            if ck in _dims_cache:
                return _dims_cache[ck]
        _pace()
        r = http.get(f"{BASE}/dataflow/{agency}/{flow}/latest", params={"references": "datastructure"},
                     headers={"Accept": "application/vnd.sdmx.structure+xml;version=2.1"})
        dims = parse_dimensions(r.text)
        with _lock:
            _dims_cache[ck] = dims
        return dims

    def fetch(self, params: dict, since: date | None) -> list[Obs]:
        agency, flow = params["agency"], params["flow"]
        dims = self.dimensions(agency, flow)
        key = ".".join(params["dims"].get(d, "") for d in dims)
        start = since or (date.today() - timedelta(days=365 * 7))
        _pace()
        r = http.get(f"{BASE}/data/{agency},{flow}/{key}",
                     params={"startPeriod": start.strftime("%Y-%m"), "format": "csvfile"})
        if not r.text.strip() or r.text.strip() == "NoResultsFound":
            return []
        return select_series(r.text, params.get("prefer") or [{}])
