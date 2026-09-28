"""Read models for the API: dashboard cards, charts, map, country panel."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

from . import db
from .adapters import ADAPTERS, CALENDARS
from .catalog import BOLLINGER, BY_ID, GROUPS, SERIES, SPREAD_CHART
from .map_catalog import IND_BY_ID, INDICATORS, all_entities, entity, load_cb_meetings, series_id
from .services.series_math import bollinger, change, value_at_or_before
from .timeutil import today_local

PERIODS = {"1M": 31, "3M": 92, "1Y": 366, "5Y": 366 * 5 + 2, "MAX": 366 * 60}
STALE_DAYS = {"D": 6, "W": 14, "M": 75, "Q": 200, "A": 800}


def _pts(sid: str, start: str | None = None) -> list[tuple[str, float]]:
    return [(r["date"], r["value"]) for r in db.get_series(sid, start)]


def series_state(sid: str, freq: str) -> dict:
    """Latest value + provenance + staleness for any series."""
    rows = db.get_series(sid)
    st = db.get_status(sid)
    out = {"value": None, "date": None, "source": st["source"] if st else None, "fetched_at": None,
           "stale": False, "stale_reason": None, "error": st["last_error"] if st else None}
    if not rows:
        if st and st["last_error"]:
            out["stale_reason"] = st["last_error"]
        return out
    last = rows[-1]
    out.update(value=last["value"], date=last["date"], source=last["source"], fetched_at=last["fetched_at"])
    if st and st["last_error"]:
        out["stale"], out["stale_reason"] = True, f"источник недоступен: {st['last_error']}"
    else:
        age = (today_local() - date.fromisoformat(last["date"])).days
        if age > STALE_DAYS.get(freq, 6):
            out["stale"], out["stale_reason"] = True, f"последнее значение {age} дн. назад"
    if st and st["last_success"]:
        out["fetched_at"] = st["last_success"]
    return out


def card(sd) -> dict:
    pts = _pts(sd.id)
    state = series_state(sd.id, sd.freq)
    start = (today_local() - timedelta(days=92)).isoformat()
    return {
        "id": sd.id, "name": sd.name, "group": sd.group, "unit": sd.unit, "freq": sd.freq,
        "decimals": sd.decimals, "change_mode": sd.change, "note": sd.note, **state,
        "changes": {
            "d1": change(pts, sd.change, 1, sd.freq),
            "w1": change(pts, sd.change, 7, sd.freq),
            "m1": change(pts, sd.change, 30, sd.freq),
        },
        "spark": [[d, v] for d, v in pts if d >= start],
    }


def dashboard() -> dict:
    from .alerts import rules_with_state
    from .ingest import fed_snapshot
    rules = rules_with_state()
    active_metrics = sorted({m for r in rules if r["active"] for m in r["metrics"]})
    lr = db.last_refresh()
    boj_next = next_cb_meeting("BOJ", "JPY")
    return {
        "groups": [{"id": g, "name": n, "cards": [card(s) for s in SERIES if s.group == g]} for g, n in GROUPS],
        "fed": fed_snapshot(),
        "boj_next_meeting": boj_next,
        "alerts": {"rules": rules, "active_metrics": active_metrics, "events": db.get_alert_events(20)},
        "last_refresh": dict(lr) if lr else None,
    }


def series_chart(sid: str, period: str) -> dict:
    days = PERIODS.get(period, 366)
    start = (today_local() - timedelta(days=days)).isoformat()
    sd = BY_ID.get(sid)
    meta = {"id": sid, "name": sd.name if sd else sid, "unit": sd.unit if sd else "",
            "decimals": sd.decimals if sd else 2, "note": sd.note if sd else ""}
    rows = db.get_series(sid, start)
    sources = sorted({r["source"] for r in rows})
    out = {**meta, "period": period, "points": [[r["date"], r["value"]] for r in rows], "sources": sources}
    if sid in BOLLINGER and rows:
        window, k = BOLLINGER[sid]
        # Band needs `window` observations before the first visible date: take a margin of calendar days.
        warm = (date.fromisoformat(rows[0]["date"]) - timedelta(days=window * 3)).isoformat()
        pts = [(r["date"], r["value"]) for r in db.get_series(sid, warm)]
        out["bands"] = {"window": window, "k": k,
                        "points": [[d, round(m, 4), round(u, 4), round(lo, 4)]
                                   for d, m, u, lo in bollinger(pts, window, k) if d >= rows[0]["date"]]}
    return out


def spread_chart(period: str) -> dict:
    return {
        "left": [series_chart(s, period) for s in SPREAD_CHART["left"]],
        "right": series_chart(SPREAD_CHART["right"], period),
    }


# ------------------------------------------------------------------ central banks / calendar
RATE_EVENT = re.compile(r"(rate decision|policy rate|cash rate|interest rate|official bank rate|"
                        r"monetary policy statement|ocr|federal funds rate|main refinancing)", re.I)


def next_cb_meeting(cb: str | None, currency: str | None) -> dict | None:
    today = today_local()
    conf = load_cb_meetings().get(cb or "", {})
    for d in conf.get("dates") or []:
        d = d if isinstance(d, date) else date.fromisoformat(str(d))
        if d >= today:
            return {"date": d.isoformat(), "source": f"Официальный календарь ЦБ ({conf.get('source')})"}
    if currency:
        start = datetime.now(timezone.utc).isoformat()
        end = (datetime.now(timezone.utc) + timedelta(days=120)).isoformat()
        for e in db.get_calendar(start, end, currencies=[currency]):
            if RATE_EVENT.search(e["title"]):
                return {"date": e["ts"], "source": e["source"], "title": e["title"]}
    return None


def rate_decisions(code: str, limit: int = 12) -> list[dict]:
    pts = _pts(series_id(code, "policy_rate"))
    out = []
    for (d0, v0), (d1, v1) in zip(pts, pts[1:]):
        if abs(v1 - v0) >= 0.005:
            out.append({"date": d1, "from": v0, "to": v1, "change_bp": round((v1 - v0) * 100)})
    return out[-limit:][::-1]


def calendar_for(c: dict, days: int = 14) -> list[dict]:
    start = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    end = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
    names = [x for x in (c.get("te"), c.get("code")) if x]
    ccy = [c["currency"]] if c.get("currency") else []
    return db.get_calendar(start, end, currencies=ccy or None, countries=names or None)


def _next_event(c: dict) -> dict | None:
    evs = calendar_for(c, 14)
    important = [e for e in evs if (e.get("impact") or "").lower() in ("high", "medium")]
    return (important or evs or [None])[0]


# ------------------------------------------------------------------ map
def _ind_state(code: str, ind: str) -> dict:
    i = IND_BY_ID[ind]
    return {"indicator": ind, "name": i.name, "unit": i.unit, "decimals": i.decimals, "note": i.note,
            **series_state(series_id(code, ind), i.freq)}


def _fx_state(c: dict) -> dict:
    if c.get("currency") == "USD":
        dxy = series_state("dxy", "D")
        pts = _pts("dxy")
        return {"quote": "DXY", "value": dxy["value"], "date": dxy["date"], "source": dxy["source"],
                "stale": dxy["stale"], "d1": change(pts, "pct", 1), "m1": change(pts, "pct", 30),
                "strength_1m": change(pts, "pct", 30), "strength_1d": change(pts, "pct", 1)}
    sid = series_id(c["code"], "fx")
    st = series_state(sid, "D")
    pts = _pts(sid)
    inv = bool(c.get("fx_inverse"))
    ccy = c["currency"]
    val = (1 / st["value"] if inv else st["value"]) if st["value"] else None

    def strength(days: int):  # % change of the currency vs USD (+ = stronger)
        ch = change(pts, "pct", days)
        return None if ch is None else round((1 / (1 + ch / 100) - 1) * 100, 3)

    s1, s30 = strength(1), strength(30)
    # change of the quoted pair as displayed
    d1 = s1 if inv else change(pts, "pct", 1)
    m1 = s30 if inv else change(pts, "pct", 30)
    return {"quote": f"{ccy}/USD" if inv else f"USD/{ccy}", "value": val, "date": st["date"],
            "source": st["source"], "stale": st["stale"], "d1": d1, "m1": m1,
            "strength_1d": s1, "strength_1m": s30}


def _summary_values(c: dict) -> dict:
    vals = {ind: _ind_state(c["code"], ind) for ind in ("policy_rate", "cpi_yoy", "y10")}
    pr, cpi = vals["policy_rate"]["value"], vals["cpi_yoy"]["value"]
    vals["real_rate"] = {
        "indicator": "real_rate", "name": "Реальная ставка (ставка ЦБ − CPI)", "unit": "%", "decimals": 2,
        "value": round(pr - cpi, 3) if pr is not None and cpi is not None else None,
        "source": "Расчёт: ставка ЦБ (BIS) − CPI г/г", "date": vals["cpi_yoy"]["date"],
        "stale": vals["policy_rate"]["stale"] or vals["cpi_yoy"]["stale"],
    }
    vals["fx"] = _fx_state(c)
    return vals


def map_summary() -> dict:
    ents = all_entities()
    base = {c["code"]: c for c in ents if not c.get("member_of")}
    ea_vals = _summary_values(base["EA"]) if "EA" in base else {}
    out = []
    for c in ents:
        member = c.get("member_of")
        vals = ea_vals if member else _summary_values(c)
        nat = {}
        if member and c.get("detail"):
            nat = {ind: _ind_state(c["code"], ind) for ind in ("cpi_yoy", "y10")}
        ev = _next_event(base.get(member, c) if member else c)
        out.append({
            "code": c["code"], "name": c["name"], "currency": c.get("currency"), "group": c.get("group"),
            "geo": c.get("geo") or [], "point": c.get("point"), "member_of": member, "note": c.get("note"),
            "values": vals, "national": nat, "next_event": ev,
        })
    return {"countries": out, "metrics": [
        {"id": "policy_rate", "name": "Ставка ЦБ", "unit": "%"},
        {"id": "cpi_yoy", "name": "Инфляция (CPI г/г)", "unit": "%"},
        {"id": "fx_1m", "name": "Валюта к USD за 1М", "unit": "%"},
        {"id": "real_rate", "name": "Реальная ставка", "unit": "%"},
    ]}


def _section(code: str, tab: str, history_years: int) -> list[dict]:
    start = (today_local() - timedelta(days=366 * history_years)).isoformat()
    items = []
    for ind in INDICATORS:
        if ind.tab != tab:
            continue
        sid = series_id(code, ind.id)
        st = _ind_state(code, ind.id)
        if st["value"] is None and not st.get("error"):
            if not db.get_status(sid):
                st["error"] = "нет бесплатного источника для этой страны"
        pts = _pts(sid, start)
        if ind.freq == "A":
            pts = [p for p in pts if int(p[0][:4]) >= today_local().year - history_years]
        items.append({**st, "history": [[d, v] for d, v in pts],
                      "forecast_from": today_local().year if ind.freq == "A" else None})
    return items


def country_detail(code: str) -> dict | None:
    c = entity(code)
    if not c:
        return None
    member = c.get("member_of")
    main = entity(member) if member else c
    cb = main.get("cb")

    def block(x: dict) -> dict:
        return {
            "code": x["code"], "name": x["name"],
            "macro": _section(x["code"], "macro", 3),
            "budget": _section(x["code"], "budget", 5),
            "micro": _section(x["code"], "micro", 3),
        }

    res = {
        "code": c["code"], "name": c["name"], "currency": c.get("currency"), "member_of": member,
        "note": main.get("note"),
        "summary": _summary_values(main),
        "cb": {"name": cb, "next_meeting": next_cb_meeting(cb, main.get("currency")),
               "decisions": rate_decisions(main["code"])},
        "blocks": [],
        "calendar": calendar_for(main, 14),
    }
    if member:
        res["blocks"].append(block(main))
        if c.get("detail"):
            res["blocks"].append(block(c))
        else:
            nat = block(c)
            nat["macro"] = [x for x in nat["macro"] if x["value"] is not None]
            nat["micro"] = []
            res["blocks"].append(nat)
    else:
        res["blocks"].append(block(c))
    return res


# ------------------------------------------------------------------ sources page
def sources() -> dict:
    rows = {r["series_id"]: dict(r) for r in db.all_status()}
    items = []
    for s in SERIES:
        r = rows.get(s.id, {})
        items.append({"series_id": s.id, "name": s.name, "group": s.group, **r,
                      "last_date": db.last_date(s.id)})
    countries = [r for k, r in rows.items() if k.startswith("c.")]
    calendars = [r for k, r in rows.items() if k.startswith("calendar.")]
    zq = [r for k, r in rows.items() if k.startswith("zq.")]
    return {
        "series": items,
        "countries": {"total": len(countries), "ok": sum(1 for r in countries if not r["last_error"]),
                      "failed": [r for r in countries if r["last_error"]]},
        "calendars": calendars + [{"series_id": f"calendar.{c.name}", "source": c.label,
                                   "last_error": "не задан ключ" if not c.available() else None}
                                  for c in CALENDARS if f"calendar.{c.name}" not in rows],
        "fed_futures": zq,
        "adapters": [{"name": a.name, "label": a.label, "homepage": a.homepage,
                      "needs_key": a.key_setting, "key_set": a.available()} for a in ADAPTERS.values()],
    }
