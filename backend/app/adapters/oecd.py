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


def select_series(text: str, prefer: list[dict], area: str | None = None) -> list[Obs]:
    """`area` — оставить строки одной страны: ответ может быть пачкой стран."""
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
        if area and r.get("REF_AREA", area) != area:
            continue
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


# Лимит OECD считается по запросам с адреса за час, и 429 тоже в него входит.
# Поэтому: страны одного датафлоу берём пачками по _BATCH в одном запросе
# (REF_AREA=USA+GBR+...), ответ держим в памяти _TTL секунд, на 429 не
# повторяем и час больше не стучимся — серии просто подождут следующего прогона.
_BATCH = 8
_TTL = 6 * 3600
_BLOCK_SEC = 3600
_data_cache: dict[str, tuple[float, str]] = {}
_blocked_until = [0.0]


def clear_cache() -> None:
    with _lock:
        _data_cache.clear()
        _blocked_until[0] = 0.0


def _batch_for(agency: str, flow: str, freq: str, area: str) -> list[str]:
    """Пачка стран из каталога, в которую попадает `area` (сама по себе — если её там нет)."""
    from ..map_catalog import country_jobs  # поздний импорт: каталог импортирует адаптеры
    areas = sorted({p["dims"]["REF_AREA"] for _, _, chain in country_jobs() for name, p in chain
                    if name == "oecd" and p["agency"] == agency and p["flow"] == flow
                    and p["dims"].get("FREQ") == freq})
    if area not in areas:
        return [area]
    i = areas.index(area) // _BATCH * _BATCH
    return areas[i:i + _BATCH]


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
        r = _get(f"{BASE}/dataflow/{agency}/{flow}/latest", params={"references": "datastructure"},
                 headers={"Accept": "application/vnd.sdmx.structure+xml;version=2.1"})
        dims = parse_dimensions(r.text)
        with _lock:
            _dims_cache[ck] = dims
        return dims

    def fetch(self, params: dict, since: date | None) -> list[Obs]:
        agency, flow = params["agency"], params["flow"]
        dims = self.dimensions(agency, flow)
        area = params["dims"].get("REF_AREA", "")
        batch = _batch_for(agency, flow, params["dims"].get("FREQ", ""), area) if area else []
        key = ".".join("+".join(batch) if d == "REF_AREA" and batch else params["dims"].get(d, "")
                       for d in dims)
        # Начало периода общее для всей пачки, чтобы ответ переиспользовался:
        # 7 лет для первой загрузки, 3 года для догрузки (перекрытие ingest меньше).
        start = date.today() - timedelta(days=365 * (7 if since is None else 3))
        url = f"{BASE}/data/{agency},{flow}/{key}"
        q = {"startPeriod": start.strftime("%Y-%m"), "format": "csvfile"}
        ck = f"{url} {q['startPeriod']}"
        with _lock:
            hit = _data_cache.get(ck)
        if hit and _time.monotonic() - hit[0] < _TTL:
            text = hit[1]
        else:
            text = _get(url, params=q).text
            with _lock:
                _data_cache[ck] = (_time.monotonic(), text)
        if not text.strip() or text.strip() == "NoResultsFound":
            return []
        return select_series(text, params.get("prefer") or [{}], area or None)


def _get(url: str, **kw):
    left = _blocked_until[0] - _time.monotonic()
    if left > 0:
        raise SourceError(f"OECD: лимит запросов исчерпан, пауза ещё {int(left // 60)} мин")
    _pace()
    try:
        return http.get(url, cache=False, retries=1, **kw)
    except SourceError as e:
        if "HTTP 429" in str(e):
            _blocked_until[0] = _time.monotonic() + _BLOCK_SEC
        raise
