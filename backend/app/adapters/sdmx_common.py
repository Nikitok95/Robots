"""Helpers shared by SDMX sources (BIS, OECD)."""
from __future__ import annotations

import re


def norm_period(p: str) -> str | None:
    """SDMX TIME_PERIOD -> ISO date of period start."""
    p = p.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p):
        return p
    m = re.fullmatch(r"(\d{4})-(\d{2})", p)
    if m:
        return f"{m[1]}-{m[2]}-01"
    m = re.fullmatch(r"(\d{4})-?Q([1-4])", p)
    if m:
        return f"{m[1]}-{(int(m[2]) - 1) * 3 + 1:02d}-01"
    m = re.fullmatch(r"(\d{4})-?S([12])", p)
    if m:
        return f"{m[1]}-{'01' if m[2] == '1' else '07'}-01"
    m = re.fullmatch(r"(\d{4})-W(\d{2})", p)
    if m:
        from datetime import date
        return date.fromisocalendar(int(m[1]), int(m[2]), 1).isoformat()
    if re.fullmatch(r"\d{4}", p):
        return f"{p}-01-01"
    return None
