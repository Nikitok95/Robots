"""Polymarket (no key): prediction-market odds.

Gamma API  — open events by tag, with current prices and 1d/1w/1m changes:
             https://gamma-api.polymarket.com/events
CLOB API   — daily price history of one outcome for the sparkline:
             https://clob.polymarket.com/prices-history
Prices are probabilities 0..1 of the «Yes» outcome of each market.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone

from .base import SourceError, http

GAMMA = "https://gamma-api.polymarket.com/events"
CLOB_HISTORY = "https://clob.polymarket.com/prices-history"
HOMEPAGE = "https://polymarket.com"
LABEL = "Polymarket"

# Section order = priority: an event tagged both «fed» and «economy» lands in the first one.
# Elections go before geopolitics: «PM of Israel after the next election» is an election.
SECTIONS: list[dict] = [
    {"id": "central_banks", "name": "Центробанки",
     "tags": ["fed-rates", "fed", "interest-rates", "ecb", "boj", "bank-of-england", "rba", "snb"], "limit": None},
    {"id": "macro", "name": "Макро",
     "tags": ["economy", "recession", "inflation", "cpi", "gdp", "unemployment", "treasuries", "commodities",
              "tariffs"], "limit": 20},
    {"id": "elections", "name": "Выборы",
     "tags": ["elections", "global-elections", "world-elections", "us-presidential-election", "midterms",
              "main-election"], "limit": None},
    {"id": "geopolitics", "name": "Геополитика", "tags": ["geopolitics"], "limit": 25},
]
MIN_VOLUME = 100_000
PAGES = 3          # up to 300 events per tag, sorted by volume
TOP_OUTCOMES = 6   # outcomes kept per event

# Выборы: только президенты, премьеры и парламенты (национальный уровень).
_ELECTION_IN = re.compile(
    r"election|nominee|prime minister|midterm|parliament|legislative|chamber of deputies|national assembly|"
    r"house in \d{4}|senate in \d{4}|balance of power|next .*government|chancellor|senate seats|house seats|"
    r"presidential runoff", re.I)
_ELECTION_OUT = re.compile(
    r"mayor|governor|ministerpr[äa]sident|state election|by-election|local election|\b[A-Z]{2}-\d{1,2}\b|"
    r"quebec|premier of|vote share|margin of victory|# of seats|over/under|drop out|scheduled|called by|"
    r"congressional maps|& house|wealth tax|on the ballot|announce|press secretary|trump out|"
    r"first round: \d|first round: margin", re.I)


# Макро: только рынки про экономику, без корпоративных и крипто-ставок.
_MACRO_OUT = re.compile(r"largest company|\bceos?\b|compan(y|ies)|\bipo|bitcoin|crypto|valuation", re.I)


def is_national_election(title: str) -> bool:
    return bool(_ELECTION_IN.search(title)) and not _ELECTION_OUT.search(title)


def _loads(v, default):
    if isinstance(v, str):
        try:
            return json.loads(v)
        except ValueError:
            return default
    return v if v is not None else default


def _f(v) -> float | None:
    try:
        return None if v is None or v == "" else float(v)
    except (TypeError, ValueError):
        return None


def parse_event(e: dict) -> dict | None:
    """Gamma event -> compact dict; None when nothing is open or priced."""
    outcomes = []
    for m in e.get("markets") or []:
        if m.get("closed") or m.get("active") is False:
            continue
        prices = _loads(m.get("outcomePrices"), [])
        names = _loads(m.get("outcomes"), [])
        tokens = _loads(m.get("clobTokenIds"), [])
        p = _f(prices[0]) if prices else None
        if p is None:
            continue
        label = (m.get("groupItemTitle") or "").strip()
        if not label:  # single yes/no market: the question itself is the outcome
            label = names[0] if len(e.get("markets") or []) > 1 and names else "Да"
        outcomes.append({
            "id": str(m.get("id")), "label": label, "question": m.get("question") or "",
            "prob": p, "d1": _f(m.get("oneDayPriceChange")), "w1": _f(m.get("oneWeekPriceChange")),
            "m1": _f(m.get("oneMonthPriceChange")), "volume": _f(m.get("volumeNum") or m.get("volume")) or 0.0,
            "token": tokens[0] if tokens else None,
        })
    if not outcomes:
        return None
    outcomes.sort(key=lambda o: -o["prob"])
    return {
        "id": str(e.get("id")), "slug": e.get("slug") or "", "title": (e.get("title") or "").strip(),
        "url": f"{HOMEPAGE}/event/{e.get('slug')}", "volume": _f(e.get("volume")) or 0.0,
        "volume_24h": _f(e.get("volume24hr")) or 0.0, "end_date": (e.get("endDate") or "")[:10] or None,
        "tags": [t.get("slug") for t in e.get("tags") or [] if t.get("slug")],
        "n_outcomes": len(outcomes), "outcomes": outcomes[:TOP_OUTCOMES],
    }


def fetch_tag(tag: str) -> list[dict]:
    out: list[dict] = []
    for page in range(PAGES):
        r = http.get(GAMMA, params={"closed": "false", "active": "true", "limit": 100, "offset": page * 100,
                                    "order": "volume", "ascending": "false", "tag_slug": tag})
        batch = r.json()
        if not isinstance(batch, list):
            raise SourceError(f"Polymarket: неожиданный ответ по тегу {tag}")
        out += batch
        # sorted by volume: once below the floor, later pages are too
        if len(batch) < 100 or (_f(batch[-1].get("volume")) or 0) < MIN_VOLUME:
            break
    return out


def collect(fetch=fetch_tag) -> list[dict]:
    """All sections: dedup (first section wins), volume floor, election filter, per-section limit."""
    seen: set[str] = set()
    result: list[dict] = []
    for sec in SECTIONS:
        items: dict[str, dict] = {}
        for tag in sec["tags"]:
            for raw in fetch(tag):
                if (_f(raw.get("volume")) or 0) < MIN_VOLUME or str(raw.get("id")) in seen:
                    continue
                title = raw.get("title") or ""
                if sec["id"] == "elections" and not is_national_election(title):
                    continue
                if sec["id"] == "macro" and _MACRO_OUT.search(title):
                    continue
                ev = parse_event(raw)
                if ev:
                    items[ev["id"]] = ev
        ranked = sorted(items.values(), key=lambda x: -x["volume"])
        if sec["limit"]:
            ranked = ranked[:sec["limit"]]
        for ev in ranked:
            seen.add(ev["id"])
            result.append({**ev, "section": sec["id"]})
    return result


def price_history(token: str, days: int = 30) -> list[tuple[str, float]]:
    start = int(time.time()) - days * 86400
    r = http.get(CLOB_HISTORY, params={"market": token, "startTs": start, "fidelity": 1440})
    hist = (r.json() or {}).get("history") or []
    out: dict[str, float] = {}
    for h in hist:
        d = datetime.fromtimestamp(int(h["t"]), tz=timezone.utc).date().isoformat()
        out[d] = float(h["p"])
    return sorted(out.items())
