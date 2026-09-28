"""Live check of every configured source: `python -m app.verify [--macro]`.
Prints status, last date and value per series. Does not write to the DB."""
from __future__ import annotations

import sys
from datetime import date, timedelta

from .adapters import ADAPTERS, CALENDARS, MissingKeyError
from .catalog import SERIES
from .ingest import fomc_dates
from .map_catalog import country_jobs
from .services.fedwatch import needed_months, zq_symbol


def check(name: str, chain: list, since: date) -> list[str]:
    lines = []
    for a, params in chain:
        if a == "alias":
            continue
        ad = ADAPTERS[a]
        label = ad.source_label(params)
        try:
            obs = ad.fetch(params, since)
            last = obs[-1] if obs else None
            lines.append(f"  OK   {label:<55} n={len(obs):<5} last={last.date if last else '-'} "
                         f"{last.value if last else ''}")
        except MissingKeyError as e:
            lines.append(f"  KEY  {label:<55} {e}")
        except Exception as e:
            lines.append(f"  FAIL {label:<55} {type(e).__name__}: {str(e)[:160]}")
    return [name] + lines


def main() -> int:
    since = date.today() - timedelta(days=45)
    failed = 0
    for s in SERIES:
        if s.derived:
            continue
        out = check(s.id, s.sources, since)
        failed += any("FAIL" in l or "KEY" in l for l in out[1:2])
        print("\n".join(out))
    print("\n# Fed funds futures (Yahoo)")
    today = date.today()
    for y, m in needed_months([d for d in fomc_dates() if d > today][:2]):
        print("\n".join(check(f"zq {y}-{m:02d}", [("yahoo", {"symbol": zq_symbol(y, m)})], since)))
    print("\n# Calendars")
    for c in CALENDARS:
        if not c.available():
            print(f"  SKIP {c.label} (нет ключа)")
            continue
        try:
            ev = c.fetch_events(today, today + timedelta(days=14))
            print(f"  OK   {c.label}: {len(ev)} событий")
        except Exception as e:
            print(f"  FAIL {c.label}: {e}")
    print("\n# Prediction markets")
    try:
        from .adapters.polymarket import collect
        evs = collect()
        by = {}
        for e in evs:
            by[e["section"]] = by.get(e["section"], 0) + 1
        print(f"  OK   Polymarket: {len(evs)} событий {by}" if evs else "  FAIL Polymarket: 0 событий")
        failed += not evs
    except Exception as e:
        print(f"  FAIL Polymarket: {e}")
        failed += 1
    if "--macro" in sys.argv:
        print("\n# Country indicators")
        for sid, ind, chain in country_jobs():
            print("\n".join(check(sid, chain, date.today() - timedelta(days=800))))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
