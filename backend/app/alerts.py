"""Alert rules. Thresholds live in the DB (editable from the UI).
Each rule is evaluated for every day of the last LOOKBACK days; events are
unique per (rule, date), so re-evaluation is idempotent."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable

from . import db
from .services.series_math import change, value_at_or_before
from .timeutil import today_local

LOOKBACK = 60


@dataclass
class RuleDef:
    id: str
    name: str
    description: str
    defaults: dict
    metrics: list[str]
    check: Callable[[dict, "Ctx", str], tuple[bool, str, dict]]


class Ctx:
    """Series cache + as-of helpers."""

    def __init__(self) -> None:
        self._cache: dict[str, list[tuple[str, float]]] = {}

    def pts(self, sid: str, upto: str | None = None) -> list[tuple[str, float]]:
        if sid not in self._cache:
            self._cache[sid] = [(r["date"], r["value"]) for r in db.get_series(sid)]
        p = self._cache[sid]
        return [x for x in p if x[0] <= upto] if upto else p

    def latest(self, sid: str, d: str, max_age: int = 4) -> tuple[str, float] | None:
        p = value_at_or_before(self.pts(sid), d)
        if p and (date.fromisoformat(d) - date.fromisoformat(p[0])).days <= max_age:
            return p
        return None


def _r1(c: Ctx, p: dict, d: str):
    """USD/JPY: yen +X% in a day AND ETF outflow on that day."""
    fx = c.pts("usdjpy", d)
    if not fx or fx[-1][0] != d:
        return False, "", {}
    ch = change(fx, "pct", 1)
    flow = c.latest("etf_flow", d, 1)
    if ch is None or flow is None:
        return False, "", {}
    ok = ch <= -abs(p["usdjpy_drop_pct"]) and flow[1] < -abs(p["etf_outflow_musd"])
    return ok, (f"Иена укрепилась: USD/JPY {ch:+.2f}% за день, отток из BTC ETF {flow[1]:+.0f} млн $"), \
        {"usdjpy_1d_pct": ch, "etf_flow_musd": flow[1]}


def _r2(c: Ctx, p: dict, d: str):
    """US 10Y real yield +X bp over a week AND MOVE rising over the week."""
    ry = c.pts("us10y_real", d)
    mv = c.pts("move", d)
    if not ry or ry[-1][0] != d or not mv:
        return False, "", {}
    ch_ry = change(ry, "bp", 7)
    ch_mv = change(mv, "abs", 7)
    if ch_ry is None or ch_mv is None:
        return False, "", {}
    ok = ch_ry > p["real_yield_bp_1w"] and ch_mv > p["move_rise_1w"]
    return ok, f"US 10Y real {ch_ry:+.0f} б.п. за неделю, MOVE {ch_mv:+.1f}", \
        {"real_yield_1w_bp": ch_ry, "move_1w": ch_mv}


def _r3(c: Ctx, p: dict, d: str):
    """ETF inflows N days in a row AND USD/JPY within a range AND funding below threshold."""
    flows = c.pts("etf_flow", d)
    n = int(p["inflow_days"])
    if len(flows) < n or flows[-1][0] != d:
        return False, "", {}
    last = [v for _, v in flows[-n:]]
    fx = c.latest("usdjpy", d)
    fnd = c.latest("funding", d, 2)
    if fx is None or fnd is None:
        return False, "", {}
    ok = all(v > 0 for v in last) and p["usdjpy_min"] <= fx[1] <= p["usdjpy_max"] and fnd[1] < p["funding_max"]
    return ok, (f"{n} дней притоков в ETF подряд, USD/JPY {fx[1]:.2f} в диапазоне, "
                f"funding {fnd[1]:.4f}%"), {"flows": last, "usdjpy": fx[1], "funding": fnd[1]}


def _r4(c: Ctx, p: dict, d: str):
    """Funding above threshold AND OI growth > X% over 3 days."""
    fnd = c.pts("funding", d)
    oi = c.pts("oi", d)
    if not fnd or fnd[-1][0] != d or not oi:
        return False, "", {}
    ch = change(oi, "pct", 3)
    if ch is None:
        return False, "", {}
    ok = fnd[-1][1] > p["funding_min"] and ch > p["oi_growth_pct_3d"]
    return ok, f"Funding {fnd[-1][1]:.4f}% и рост OI {ch:+.1f}% за 3 дня — перегрев плеча", \
        {"funding": fnd[-1][1], "oi_3d_pct": ch}


RULES: list[RuleDef] = [
    RuleDef("yen_squeeze_etf_outflow", "Укрепление иены + отток из ETF",
            "USD/JPY падает сильнее порога за день И нетто-отток из spot BTC ETF в тот же день",
            {"usdjpy_drop_pct": 1.5, "etf_outflow_musd": 0}, ["usdjpy", "etf_flow"], _r1),
    RuleDef("real_yield_move", "Рост реальной доходности + MOVE",
            "US 10Y real yield растёт больше порога (б.п.) за неделю И индекс MOVE растёт за неделю",
            {"real_yield_bp_1w": 10, "move_rise_1w": 0}, ["us10y_real", "move"], _r2),
    RuleDef("carry_risk_on", "Риск-он: притоки ETF + стабильная иена",
            "Притоки в ETF N дней подряд И USD/JPY в диапазоне И funding ниже порога",
            {"inflow_days": 5, "usdjpy_min": 140, "usdjpy_max": 155, "funding_max": 0.01},
            ["etf_flow", "usdjpy", "funding"], _r3),
    RuleDef("leverage_buildup", "Перегрев плеча в перпетуалах",
            "Funding rate выше порога И рост Open Interest больше X% за 3 дня",
            {"funding_min": 0.03, "oi_growth_pct_3d": 5}, ["funding", "oi"], _r4),
]
RULES_BY_ID = {r.id: r for r in RULES}


def seed_rules() -> None:
    for r in RULES:
        db.seed_rule(r.id, r.name, r.description, r.defaults)


def rules_with_state() -> list[dict]:
    ctx = Ctx()
    today = today_local().isoformat()
    out = []
    for row in db.get_rules():
        rd = RULES_BY_ID.get(row["id"])
        if not rd:
            continue
        params = {**rd.defaults, **row["params"]}
        active, msg = False, ""
        # "active" = condition true on the latest day that has data (up to 4 days back)
        for i in range(0, 5):
            d = (date.fromisoformat(today) - timedelta(days=i)).isoformat()
            ok, m, _ = rd.check(ctx, params, d)
            if m:
                active, msg = ok, m
                break
        out.append({**row, "params": params, "metrics": rd.metrics, "active": active and row["enabled"],
                    "last_message": msg})
    return out


def evaluate_all(lookback: int = LOOKBACK) -> int:
    ctx = Ctx()
    new = 0
    today = today_local()
    for row in db.get_rules():
        rd = RULES_BY_ID.get(row["id"])
        if not rd or not row["enabled"]:
            continue
        params = {**rd.defaults, **row["params"]}
        for i in range(lookback, -1, -1):
            d = (today - timedelta(days=i)).isoformat()
            ok, msg, details = rd.check(ctx, params, d)
            if ok and db.insert_alert_event(rd.id, d, msg, {**details, "params": params}):
                new += 1
    return new
