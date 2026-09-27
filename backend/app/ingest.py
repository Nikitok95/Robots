"""Fetch → cache → derive. Incremental: only dates after the last stored one
(minus a small overlap for revisions) are requested."""
from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

from . import db
from .adapters import ADAPTERS, CALENDARS, MissingKeyError, SourceError, http
from .catalog import BY_ID, SERIES
from .map_catalog import country_jobs, load_cb_meetings
from .services import fedwatch
from .services.series_math import align, diff_series, realized_vol, rolling_sum, value_at_or_before
from .timeutil import today_local

log = logging.getLogger(__name__)

OVERLAP = {"D": 10, "W": 35, "M": 120, "Q": 400, "A": 3 * 366}
MIN_INTERVAL_H = {"D": 0, "W": 12, "M": 20, "Q": 20, "A": 20}
_job_lock = threading.Lock()
running: dict[str, bool] = {}


def _since(series_id: str, freq: str) -> date | None:
    last = db.last_date(series_id)
    if not last:
        return None
    return date.fromisoformat(last) - timedelta(days=OVERLAP.get(freq, 10))


def _recent_success(series_id: str, freq: str) -> bool:
    st = db.get_status(series_id)
    h = MIN_INTERVAL_H.get(freq, 0)
    if not h or not st or not st["last_success"] or st["last_error"]:
        return False
    age = datetime.now(timezone.utc) - datetime.fromisoformat(st["last_success"])
    return age < timedelta(hours=h)


def fetch_series(series_id: str, freq: str, chain: list[tuple[str, dict]], force: bool = False) -> bool:
    """Try each source in order; store the first successful result."""
    if not force and _recent_success(series_id, freq):
        return True
    errors = []
    for name, params in chain:
        if name == "alias":
            rows = db.get_series(params["series"])
            if rows:
                src = rows[-1]["source"]
                db.upsert_observations(series_id, [(r["date"], r["value"]) for r in rows], src)
                db.set_status(series_id, src, None)
                return True
            errors.append(f"alias {params['series']}: нет данных")
            continue
        adapter = ADAPTERS[name]
        label = adapter.source_label(params)
        try:
            obs = adapter.fetch(params, _since(series_id, freq))
        except MissingKeyError as e:
            errors.append(str(e))
            continue
        except SourceError as e:
            errors.append(f"{label}: {e}")
            continue
        except Exception as e:  # parsing bugs must not kill the whole run
            log.exception("adapter %s failed", name)
            errors.append(f"{label}: {type(e).__name__}: {e}")
            continue
        if not obs and db.last_date(series_id) is None:
            errors.append(f"{label}: пустой ответ")
            continue
        db.upsert_observations(series_id, [(o.date, o.value) for o in obs], label)
        db.set_status(series_id, label, None)
        return True
    first_label = ADAPTERS[chain[0][0]].source_label(chain[0][1]) if chain and chain[0][0] in ADAPTERS else "—"
    db.set_status(series_id, first_label, " | ".join(errors) or "нет источника")
    return False


def _pts(series_id: str, start: str | None = None) -> list[tuple[str, float]]:
    return [(r["date"], r["value"]) for r in db.get_series(series_id, start)]


def _store_derived(series_id: str, points: list[tuple[str, float]]) -> None:
    sd = BY_ID[series_id]
    if points:
        db.upsert_observations(series_id, points, sd.derived_label)
        db.set_status(series_id, sd.derived_label, None)
    else:
        db.set_status(series_id, sd.derived_label, "недостаточно исходных данных")


def compute_derived(job: str) -> None:
    if job in ("markets", "all"):
        _store_derived("spread_2y", diff_series(_pts("us2y"), _pts("jgb2y")))
        _store_derived("spread_10y", diff_series(_pts("us10y"), _pts("jgb10y")))
        _store_derived("usdjpy_rv30", realized_vol(_pts("usdjpy"), 30))
        _store_derived("boj_implied_bp", [(d, round(v * 100, 2)) for d, v in
                                          diff_series(_pts("jgb1y"), _pts("boj_rate"))])
        update_fedwatch()
    if job in ("crypto", "all"):
        _store_derived("etf_flow_5d", rolling_sum(_pts("etf_flow"), 5))
        prem = [(d, round((cb - bn) / bn * 100, 5)) for d, cb, bn in
                align(_pts("cb_close"), _pts("bn_close"), 0) if bn]
        _store_derived("cb_premium", prem)


# ---------------------------------------------------------------- fed funds futures
def fomc_dates() -> list[date]:
    return [d if isinstance(d, date) else date.fromisoformat(str(d))
            for d in (load_cb_meetings().get("FED", {}).get("dates") or [])]


def fed_snapshot(as_of: date | None = None) -> dict:
    """Probabilities for the next two FOMC meetings as of a date."""
    as_of = as_of or today_local()
    meetings = [d for d in fomc_dates() if d > as_of][:2]
    if not meetings:
        return {"error": "нет будущих дат FOMC в config/cb_meetings.yaml"}
    d = as_of.isoformat()
    effr = value_at_or_before(_pts("effr"), d)
    lo = value_at_or_before(_pts("fed_lower"), d)
    hi = value_at_or_before(_pts("fed_upper"), d)
    if not (effr and lo and hi):
        return {"error": "нет EFFR / диапазона ставки ФРС (FRED)"}
    prices, sources = {}, {}
    for y, m in fedwatch.needed_months(meetings):
        key = f"{y}-{m:02d}"
        p = value_at_or_before(_pts(f"zq.{key}"), d)
        if p and (as_of - date.fromisoformat(p[0])).days <= 7:
            prices[key] = p[1]
            sources[key] = fedwatch.zq_symbol(y, m)
    res = fedwatch.compute(meetings, effr[1], lo[1], hi[1], prices)
    return {"as_of": d, "effr": effr[1], "target": [lo[1], hi[1]], "meetings": res,
            "contracts": sources, "source": BY_ID["fed_next_exp_bp"].derived_label}


def update_fedwatch() -> None:
    today = today_local()
    months = set()
    for d in [x for x in fomc_dates() if x > today - timedelta(days=120)][:4]:
        months.update(fedwatch.needed_months([d]))
    for y, m in sorted(months):
        sym = fedwatch.zq_symbol(y, m)
        fetch_series(f"zq.{y}-{m:02d}", "D", [("yahoo", {"symbol": sym})], force=True)
    pts = []
    for i in range(90, -1, -1):
        d = today - timedelta(days=i)
        if d.weekday() >= 5:
            continue
        snap = fed_snapshot(d)
        ms = snap.get("meetings") or []
        if ms and "expected_change_bp" in ms[0]:
            pts.append((d.isoformat(), ms[0]["expected_change_bp"]))
    _store_derived("fed_next_exp_bp", pts)


# ---------------------------------------------------------------- calendar
def refresh_calendar() -> tuple[int, int]:
    start = today_local() - timedelta(days=1)
    end = start + timedelta(days=16)
    ok = failed = 0
    for cal in CALENDARS:
        if not cal.available():
            continue
        sid = f"calendar.{cal.name}"
        try:
            events = cal.fetch_events(start, end)
            db.upsert_calendar(events, cal.label)
            db.set_status(sid, cal.label, None)
            ok += 1
        except Exception as e:
            db.set_status(sid, cal.label, str(e))
            failed += 1
    return ok, failed


# ---------------------------------------------------------------- jobs
def _run_many(tasks: list[tuple[str, str, list]], force: bool) -> tuple[int, int]:
    ok = failed = 0
    with ThreadPoolExecutor(max_workers=6) as ex:
        for res in ex.map(lambda t: fetch_series(t[0], t[1], t[2], force), tasks):
            ok, failed = (ok + 1, failed) if res else (ok, failed + 1)
    return ok, failed


def run_job(job: str, force: bool = False) -> dict:
    """job: markets | crypto | macro | all"""
    with _job_lock:
        if running.get(job):
            return {"job": job, "status": "already running"}
        running[job] = True
    log_id = db.log_refresh_start(job)
    ok = failed = 0
    try:
        http.clear_cache()
        jobs = ["markets", "crypto", "macro"] if job == "all" else [job]
        for j in jobs:
            if j in ("markets", "crypto"):
                tasks = [(s.id, s.freq, s.sources) for s in SERIES if s.job == j and not s.derived]
                a, b = _run_many(tasks, force)
                ok, failed = ok + a, failed + b
                compute_derived(j)
            elif j == "macro":
                tasks = [(sid, ind.freq, chain) for sid, ind, chain in country_jobs()]
                a, b = _run_many(tasks, force)
                c, d = refresh_calendar()
                ok, failed = ok + a + c, failed + b + d
        from .alerts import evaluate_all
        evaluate_all()
    finally:
        db.log_refresh_end(log_id, ok, failed)
        running[job] = False
    log.info("refresh %s: ok=%s failed=%s", job, ok, failed)
    return {"job": job, "ok": ok, "failed": failed}
