"""Pure helpers on (date, value) lists — easy to unit test."""
from __future__ import annotations

import bisect
import math
from datetime import date, timedelta

Point = tuple[str, float]


def value_at_or_before(points: list[Point], d: str) -> Point | None:
    dates = [p[0] for p in points]
    i = bisect.bisect_right(dates, d)
    return points[i - 1] if i else None


def align(a: list[Point], b: list[Point], max_gap_days: int = 5) -> list[tuple[str, float, float]]:
    """For each date of `a`, take the latest value of `b` not older than max_gap_days."""
    out = []
    for d, va in a:
        pb = value_at_or_before(b, d)
        if pb and (date.fromisoformat(d) - date.fromisoformat(pb[0])).days <= max_gap_days:
            out.append((d, va, pb[1]))
    return out


def diff_series(a: list[Point], b: list[Point]) -> list[Point]:
    return [(d, round(x - y, 6)) for d, x, y in align(a, b)]


def rolling_sum(points: list[Point], n: int) -> list[Point]:
    return [(points[i][0], round(sum(v for _, v in points[i - n + 1:i + 1]), 6))
            for i in range(n - 1, len(points))]


def realized_vol(points: list[Point], window: int = 30, annualize: int = 252) -> list[Point]:
    rets = [(points[i][0], math.log(points[i][1] / points[i - 1][1]))
            for i in range(1, len(points)) if points[i - 1][1] > 0 and points[i][1] > 0]
    out = []
    for i in range(window - 1, len(rets)):
        w = [r for _, r in rets[i - window + 1:i + 1]]
        m = sum(w) / window
        var = sum((r - m) ** 2 for r in w) / (window - 1)
        out.append((rets[i][0], round(math.sqrt(var) * math.sqrt(annualize) * 100, 4)))
    return out


def change(points: list[Point], mode: str, days: int, freq: str = "D") -> float | None:
    """Change of the last value vs. the value `days` calendar days earlier.
    days == 1 means "previous observation" for daily series."""
    if len(points) < 2:
        return None
    d0, v0 = points[-1]
    if days == 1:
        if freq != "D":
            return None
        ref = points[-2]
    else:
        target = (date.fromisoformat(d0) - timedelta(days=days)).isoformat()
        ref = value_at_or_before(points, target)
        if ref is None:
            return None
    v = ref[1]
    if mode == "bp":
        return round((v0 - v) * 100, 2)
    if mode == "pct":
        return round((v0 / v - 1) * 100, 3) if v else None
    return round(v0 - v, 6)
