from datetime import date, timedelta

import httpx
import respx
from fastapi.testclient import TestClient

from app import db
from app.ingest import fetch_series
from app.timeutil import today_local


def _days(n):
    t = today_local()
    return [(t - timedelta(days=n - 1 - i)).isoformat() for i in range(n)]


@respx.mock
def test_fallback_chain_records_source_and_stale():
    respx.get(url__regex=r".*yahoo.*").mock(return_value=httpx.Response(503))
    respx.get("https://api.stlouisfed.org/fred/series/observations").mock(return_value=httpx.Response(
        200, json={"observations": [{"date": today_local().isoformat(), "value": "148.1"}]}))
    assert fetch_series("usdjpy", "D", [("yahoo", {"symbol": "JPY=X"}), ("fred", {"series_id": "DEXJPUS"})])
    row = db.get_series("usdjpy")[-1]
    assert row["value"] == 148.1 and row["source"] == "FRED · DEXJPUS"

    # now every source fails -> last value kept, status carries the error
    respx.get("https://api.stlouisfed.org/fred/series/observations").mock(return_value=httpx.Response(500))
    assert not fetch_series("usdjpy", "D", [("fred", {"series_id": "DEXJPUS"})])
    from app.views import series_state
    st = series_state("usdjpy", "D")
    assert st["value"] == 148.1 and st["stale"] and "недоступен" in st["stale_reason"]


@respx.mock
def test_incremental_since():
    route = respx.get("https://api.stlouisfed.org/fred/series/observations").mock(
        return_value=httpx.Response(200, json={"observations": []}))
    db.upsert_observations("us2y", [("2026-09-01", 3.5)], "FRED · DGS2")
    fetch_series("us2y", "D", [("fred", {"series_id": "DGS2"})])
    assert route.calls[0].request.url.params["observation_start"] == "2026-08-22"


def test_alert_rule_triggers_and_api():
    from app.alerts import evaluate_all, seed_rules
    seed_rules()
    days = _days(8)
    # rule 4: funding above 0.03 and OI +10% over 3 days
    db.upsert_observations("funding", [(d, 0.05) for d in days], "t")
    db.upsert_observations("oi", [(d, 100 + 5 * i) for i, d in enumerate(days)], "t")
    # rule 1: USD/JPY -2% and ETF outflow on the last day
    db.upsert_observations("usdjpy", [(d, 150.0) for d in days[:-1]] + [(days[-1], 147.0)], "t")
    db.upsert_observations("etf_flow", [(days[-1], -300.0)], "t")
    assert evaluate_all() >= 2
    from app.main import app
    with TestClient(app) as c:
        ev = c.get("/api/alerts/events").json()
        assert {e["rule_id"] for e in ev} >= {"leverage_buildup", "yen_squeeze_etf_outflow"}
        rules = {r["id"]: r for r in c.get("/api/alerts/rules").json()}
        assert rules["leverage_buildup"]["active"]
        # raising the threshold switches the rule off
        r = c.put("/api/alerts/rules/leverage_buildup", json={"params": {"funding_min": 0.1}}).json()
        assert r["params"]["funding_min"] == 0.1 and not r["active"]
        dash = c.get("/api/dashboard").json()
        assert [g["id"] for g in dash["groups"]] == ["rates", "spreads", "fx", "crypto", "risk"]
        assert "usdjpy" in dash["alerts"]["active_metrics"]
        card = next(x for g in dash["groups"] for x in g["cards"] if x["id"] == "usdjpy")
        assert card["changes"]["d1"] == -2.0 and card["source"] == "t"
        m = c.get("/api/map").json()
        assert any(x["code"] == "DE" and x["member_of"] == "EA" for x in m["countries"])
        d = c.get("/api/map/country/DE").json()
        assert [b["code"] for b in d["blocks"]] == ["EA", "DE"]
        assert c.get("/api/map/country/XX").status_code == 404
        assert c.get("/api/series/usdjpy?period=1M").json()["points"]
        assert "series" in c.get("/api/sources").json()
