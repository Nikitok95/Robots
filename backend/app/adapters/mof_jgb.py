"""Japan Ministry of Finance JGB benchmark yields (CSV, no key).
https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/index.htm
Current month: jgbcme.csv, history: historical/jgbcme_all.csv
Columns: Date,1Y,2Y,...,10Y,15Y,20Y,25Y,30Y,40Y. "-" = no value."""
from __future__ import annotations

import csv
import io
import re
from datetime import date

from .base import Obs, SourceAdapter, SourceError, http, to_float

BASE = "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/"
CURRENT = BASE + "jgbcme.csv"
HISTORY = BASE + "historical/jgbcme_all.csv"

ERAS = {"S": 1925, "H": 1988, "R": 2018}
_greg = re.compile(r"^(\d{4})[/-](\d{1,2})[/-](\d{1,2})$")
_era = re.compile(r"^([SHR])(\d{1,2})\.(\d{1,2})\.(\d{1,2})$")


def parse_date(s: str) -> str | None:
    s = s.strip()
    m = _greg.match(s)
    if m:
        y, mo, d = map(int, m.groups())
        return date(y, mo, d).isoformat()
    m = _era.match(s)
    if m:
        era, y, mo, d = m.groups()
        return date(ERAS[era] + int(y), int(mo), int(d)).isoformat()
    return None


def decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp932"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def parse_csv(text: str, tenor: str) -> list[Obs]:
    rows = list(csv.reader(io.StringIO(text)))
    header_idx = next((i for i, r in enumerate(rows) if r and r[0].strip() in ("Date", "基準日")), None)
    if header_idx is None:
        raise SourceError("MoF CSV: не найдена строка заголовка")
    header = [h.strip() for h in rows[header_idx]]
    if tenor not in header:
        raise SourceError(f"MoF CSV: нет колонки {tenor}; есть {header}")
    col = header.index(tenor)
    out = []
    for r in rows[header_idx + 1:]:
        if len(r) <= col:
            continue
        d = parse_date(r[0])
        v = to_float(r[col])
        if d and v is not None:
            out.append(Obs(d, v))
    return out


class MofJgbAdapter(SourceAdapter):
    name = "mof_jgb"
    label = "Минфин Японии"
    homepage = "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/index.htm"

    def source_label(self, params: dict) -> str:
        return f"{self.label} · JGB {params['tenor']}"

    def fetch(self, params: dict, since: date | None) -> list[Obs]:
        tenor = params["tenor"]
        today = date.today()
        month_start = today.replace(day=1)
        out = parse_csv(decode(http.get(CURRENT).content), tenor)
        if since is None or since < month_start:
            try:
                out = parse_csv(decode(http.get(HISTORY).content), tenor) + out
            except SourceError:
                if since is None:
                    raise
        if since:
            out = [o for o in out if o.date >= since.isoformat()]
        return sorted({o.date: o for o in out}.values(), key=lambda o: o.date)
