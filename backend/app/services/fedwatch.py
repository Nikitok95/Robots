"""Fed decision probabilities from 30-Day Fed Funds futures (CME ZQ, prices via
Yahoo Finance). Simplified CME FedWatch method:
  implied monthly average  r_avg = 100 - price
  meeting month:  r_end = (N * r_avg - m * r_start) / (N - m)  (m = days before
                  the new rate is effective, i.e. the decision day)
  late meeting (<7 days left): use next month's contract as r_end
  probabilities: expected change in 25bp steps split between floor/ceil."""
from __future__ import annotations

import calendar
import math
from datetime import date

MONTH_CODES = "FGHJKMNQUVXZ"


def zq_symbol(year: int, month: int) -> str:
    return f"ZQ{MONTH_CODES[month - 1]}{year % 100:02d}.CBT"


def month_key(d: date) -> str:
    return f"{d.year}-{d.month:02d}"


def next_month(y: int, m: int) -> tuple[int, int]:
    return (y + 1, 1) if m == 12 else (y, m + 1)


def needed_months(meetings: list[date]) -> list[tuple[int, int]]:
    out = set()
    for d in meetings:
        out.add((d.year, d.month))
        out.add(next_month(d.year, d.month))
    return sorted(out)


def compute(meetings: list[date], effr: float, target_low: float, target_high: float,
            prices: dict[str, float]) -> list[dict]:
    """meetings: next meetings (sorted). prices: {"YYYY-MM": ZQ price}.
    Returns per meeting: expected rate, change vs. now (bp), distribution."""
    meeting_months = {(d.year, d.month) for d in meetings}
    r_start = effr
    results = []
    for d in meetings:
        n = calendar.monthrange(d.year, d.month)[1]
        m = d.day  # new rate effective the day after the decision
        key = month_key(d)
        ny, nm = next_month(d.year, d.month)
        nkey = f"{ny}-{nm:02d}"
        r_end = None
        if n - m < 7 and nkey in prices and (ny, nm) not in meeting_months:
            r_end = 100 - prices[nkey]
        elif key in prices:
            r_avg = 100 - prices[key]
            r_end = (n * r_avg - m * r_start) / (n - m)
        elif nkey in prices:
            r_end = 100 - prices[nkey]
        if r_end is None:
            results.append({"date": d.isoformat(), "error": f"нет цены контракта {zq_symbol(d.year, d.month)}"})
            continue
        cum_bp = (r_end - effr) * 100
        steps = cum_bp / 25
        lo = math.floor(steps)
        frac = steps - lo
        dist = []
        for k, p in ((lo, 1 - frac), (lo + 1, frac)):
            if p < 0.005:
                continue
            dist.append({
                "low": round(target_low + k * 0.25, 2), "high": round(target_high + k * 0.25, 2),
                "change_bp": k * 25, "prob": round(p, 4),
            })
        meeting_change = (r_end - r_start) * 100
        results.append({
            "date": d.isoformat(), "implied_rate": round(r_end, 4),
            "expected_change_bp": round(meeting_change, 1), "cumulative_change_bp": round(cum_bp, 1),
            "distribution": sorted(dist, key=lambda x: x["change_bp"]),
        })
        r_start = r_end
    return results
