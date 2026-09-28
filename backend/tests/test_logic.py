from datetime import date, timedelta

import pytest

from app.services import fedwatch
from app.services.series_math import change, diff_series, realized_vol, rolling_sum


def test_change_modes():
    pts = [("2026-08-20", 4.0), ("2026-09-14", 4.1), ("2026-09-21", 4.2), ("2026-09-22", 4.3)]
    assert change(pts, "bp", 1) == pytest.approx(10)
    assert change(pts, "bp", 7) == pytest.approx(20)       # vs 2026-09-14
    assert change(pts, "pct", 30) == pytest.approx(7.5)   # vs 2026-08-20
    assert change(pts, "abs", 1, "W") is None              # no 1D for weekly


def test_rolling_and_diff():
    assert rolling_sum([("a", 1), ("b", 2), ("c", 3)], 2) == [("b", 3), ("c", 5)]
    us = [("2026-09-18", 3.6), ("2026-09-21", 3.5)]
    jp = [("2026-09-18", 0.9)]
    assert diff_series(us, jp) == [("2026-09-18", 2.7), ("2026-09-21", 2.6)]


def test_realized_vol_constant_returns_zero():
    pts = [(f"d{i:03d}", 100 * 1.001 ** i) for i in range(40)]
    rv = realized_vol(pts, 30)
    assert len(rv) == 10 and rv[-1][1] == pytest.approx(0, abs=1e-6)


def test_zq_symbol():
    assert fedwatch.zq_symbol(2026, 10) == "ZQV26.CBT"
    assert fedwatch.zq_symbol(2027, 1) == "ZQF27.CBT"


def test_fedwatch_certain_cut_and_hold():
    # Oct 28 meeting, 31 days: 28 days at 4.08, 3 days at 3.83 -> avg
    effr = 4.08
    avg_oct = (28 * 4.08 + 3 * 3.83) / 31
    # Dec 9 meeting (31 days): no further change
    prices = {"2026-10": 100 - avg_oct, "2026-11": 100 - 3.83, "2026-12": 100 - 3.83}
    res = fedwatch.compute([date(2026, 10, 28), date(2026, 12, 9)], effr, 4.0, 4.25, prices)
    # late-month meeting -> November contract used
    assert res[0]["expected_change_bp"] == pytest.approx(-25, abs=0.1)
    assert res[0]["distribution"] == [{"low": 3.75, "high": 4.0, "change_bp": -25, "prob": 1.0}]
    assert res[1]["expected_change_bp"] == pytest.approx(0, abs=0.1)


def test_fedwatch_partial_probability():
    prices = {"2026-12": 100 - (9 * 3.83 + 22 * (3.83 - 0.125)) / 31, "2027-01": 100 - 3.705}
    res = fedwatch.compute([date(2026, 12, 9)], 3.83, 3.75, 4.0, prices)
    dist = {d["change_bp"]: d["prob"] for d in res[0]["distribution"]}
    assert dist[-25] == pytest.approx(0.5, abs=0.01) and dist[0] == pytest.approx(0.5, abs=0.01)


def test_fedwatch_missing_contract():
    res = fedwatch.compute([date(2026, 10, 28)], 4.08, 4.0, 4.25, {})
    assert "error" in res[0]


def test_bollinger_bands():
    from app.services.series_math import bollinger
    pts = [(f"2026-09-{d:02d}", v) for d, v in zip(range(1, 6), [1.0, 2.0, 3.0, 4.0, 5.0])]
    bands = bollinger(pts, window=3, k=0.7)
    assert [b[0] for b in bands] == ["2026-09-03", "2026-09-04", "2026-09-05"]  # no band before the window fills
    d, mid, up, lo = bands[0]
    sd = (2 / 3) ** 0.5  # population σ of 1, 2, 3
    assert mid == pytest.approx(2.0) and up == pytest.approx(2 + 0.7 * sd) and lo == pytest.approx(2 - 0.7 * sd)
    assert bollinger(pts[:2], window=3, k=0.7) == []


def test_series_chart_bands_only_for_treasuries():
    from app import db
    from app.catalog import BOLLINGER
    from app.timeutil import today_local
    from app.views import series_chart
    today = today_local()
    rows = [((today - timedelta(days=i)).isoformat(), 4.0 + (i % 5) * 0.01) for i in range(120, -1, -1)]
    db.upsert_observations("us10y", rows, "FRED")
    db.upsert_observations("vix", rows, "FRED")
    ch = series_chart("us10y", "1M")
    assert BOLLINGER["us10y"] == (20, 0.7) and ch["bands"]["k"] == 0.7 and ch["bands"]["window"] == 20
    # warm-up history: the band starts at the first visible date, not 20 points later
    assert ch["bands"]["points"][0][0] == ch["points"][0][0]
    assert all(lo <= mid <= up for _, mid, up, lo in ch["bands"]["points"])
    assert "bands" not in series_chart("vix", "1M")
