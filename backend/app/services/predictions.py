"""Prediction markets (Polymarket): hourly snapshot + comparison with fed funds futures."""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta, timezone

from .. import db
from ..adapters import polymarket as pm

log = logging.getLogger(__name__)

STATUS_ID = "predictions.polymarket"
HISTORY_TTL = timedelta(hours=6)
_MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july",
                                       "august", "september", "october", "november", "december"], 1)}


def _fresh(at: str | None) -> bool:
    if not at:
        return False
    return datetime.now(timezone.utc) - datetime.fromisoformat(at) < HISTORY_TTL


def refresh(collect=pm.collect, history=pm.price_history) -> bool:
    """Replace the stored snapshot. Keeps the last good one when Polymarket is down."""
    try:
        events = collect()
    except Exception as e:  # network / format: the old snapshot stays on screen
        log.warning("polymarket: %s", e)
        db.set_status(STATUS_ID, pm.LABEL, str(e))
        return False
    old = {e["id"]: e for e in db.get_predictions()}
    now = db.utcnow_iso()
    for ev in events:
        token = ev["outcomes"][0].get("token")
        prev = old.get(ev["id"])
        if prev and prev.get("history_token") == token and _fresh(prev.get("history_at")):
            ev.update(history=prev["history"], history_token=token, history_at=prev["history_at"])
            continue
        if not token:
            continue
        try:
            ev.update(history=[[d, p] for d, p in history(token)], history_token=token, history_at=now)
        except Exception as e:  # a sparkline is optional
            log.info("polymarket history %s: %s", ev["id"], e)
            if prev and prev.get("history_token") == token:
                ev.update(history=prev["history"], history_token=token, history_at=prev.get("history_at"))
    db.replace_predictions(events)
    db.set_status(STATUS_ID, pm.LABEL, None if events else "нет событий выше порога объёма")
    return bool(events)


def outcome_bp(label: str) -> tuple[int, bool] | None:
    """«25 bps decrease» → (-25, False); «50+ bps increase» → (50, True); «No change» → (0, False)."""
    s = label.lower()
    if "no change" in s:
        return 0, False
    m = re.search(r"(\d+)\s*(\+)?\s*bps?\s*(decrease|cut|increase|hike)", s)
    if not m:
        return None
    n = int(m.group(1)) * (-1 if m.group(3) in ("decrease", "cut") else 1)
    return n, bool(m.group(2))


def fed_compare(events: list[dict], fed: dict) -> dict | None:
    """Polymarket odds for the next FOMC vs the futures-implied distribution."""
    meetings = fed.get("meetings") or []
    if not meetings:
        return None
    meeting = meetings[0]
    md = date.fromisoformat(meeting["date"])
    ev = None
    for e in events:
        m = re.match(r"fed decision in (\w+)", e["title"].lower())
        if m and _MONTHS.get(m.group(1)) == md.month and e.get("end_date", "")[:4] in ("", str(md.year), str(md.year + (md.month == 12))):
            ev = e
            break
    if not ev:
        return None
    futures = meeting.get("distribution") or []
    rows = []
    for o in ev["outcomes"]:
        parsed = outcome_bp(o["label"])
        if parsed is None:
            continue
        bp, plus = parsed
        if plus:
            fut = sum(d["prob"] for d in futures if (d["change_bp"] >= bp if bp > 0 else d["change_bp"] <= bp))
        else:
            fut = sum(d["prob"] for d in futures if d["change_bp"] == bp)
        rows.append({"label": o["label"], "change_bp": bp, "plus": plus, "polymarket": o["prob"],
                     "futures": fut if futures else None})
    rows.sort(key=lambda r: r["change_bp"])
    return {"meeting": meeting["date"], "event": ev["title"], "url": ev["url"], "rows": rows,
            "futures_error": meeting.get("error")}


def snapshot(fed: dict) -> dict:
    events = db.get_predictions()
    st = db.get_status(STATUS_ID)
    sections = []
    for sec in pm.SECTIONS:
        items = [{k: v for k, v in e.items() if k not in ("history_token", "history_at")}
                 for e in events if e["section"] == sec["id"]]
        sections.append({"id": sec["id"], "name": sec["name"], "events": items})
    return {
        "sections": sections,
        "fed_compare": fed_compare([e for e in events if e["section"] == "central_banks"], fed),
        "fetched_at": events[0]["fetched_at"] if events else None,
        "error": st["last_error"] if st else None,
        "source": pm.LABEL, "homepage": pm.HOMEPAGE, "min_volume": pm.MIN_VOLUME,
    }
