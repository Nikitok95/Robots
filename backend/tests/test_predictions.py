"""Polymarket: parsing, selection rules, snapshot storage, Fed comparison."""
import json

import httpx
import respx

from app import db
from app.adapters import polymarket as pm
from app.services import predictions as svc


def _market(mid, label, p, closed=False, **kw):
    return {"id": mid, "groupItemTitle": label, "question": f"{label}?", "outcomes": '["Yes", "No"]',
            "outcomePrices": json.dumps([str(p), str(round(1 - p, 4))]), "clobTokenIds": f'["tok{mid}", "no{mid}"]',
            "volumeNum": 1000, "closed": closed, "active": True, "oneDayPriceChange": 0.01, **kw}


def _event(eid, title, volume, markets, tags=()):
    return {"id": eid, "slug": f"s{eid}", "title": title, "volume": volume, "endDate": "2026-10-29T00:00:00Z",
            "markets": markets, "tags": [{"slug": t} for t in tags]}


FED_OCT = _event("1", "Fed Decision in October?", 15e6, [
    _market("a", "50+ bps decrease", 0.0025), _market("b", "25 bps decrease", 0.0045),
    _market("c", "No change", 0.285), _market("d", "25 bps increase", 0.705),
    _market("e", "50+ bps increase", 0.0085), _market("f", "old", 0.9, closed=True)])


def test_parse_event_sorts_open_outcomes_and_skips_closed():
    ev = pm.parse_event(FED_OCT)
    assert [o["label"] for o in ev["outcomes"]][:2] == ["25 bps increase", "No change"]
    assert "old" not in [o["label"] for o in ev["outcomes"]]
    assert ev["url"] == "https://polymarket.com/event/s1" and ev["outcomes"][0]["token"] == "tokd"


def test_single_yes_no_market_gets_label():
    ev = pm.parse_event(_event("2", "US recession by end of 2026?", 2e6, [_market("x", "", 0.08)]))
    assert ev["outcomes"][0]["label"] == "Да" and ev["outcomes"][0]["prob"] == 0.08


def test_election_filter_keeps_national_drops_local():
    keep = ["Presidential Election Winner 2028", "Next Prime Minister of Sweden", "Which party will win the House in 2026?",
            "Lebanon Parliamentary Election Winner", "Democratic Presidential Nominee 2028", "Maine Senate Election Winner"]
    drop = ["Los Angeles Mayoral Election", "California Governor Election Winner", "CA-28 House Election Winner",
            "Next Ministerpräsident of Sachsen-Anhalt?", "Trump out as President before 2027?",
            "Brazil Presidential Election First Round: Margin of Victory", "Next Premier of Quebec"]
    assert all(pm.is_national_election(t) for t in keep)
    assert not any(pm.is_national_election(t) for t in drop)


def test_collect_dedups_by_section_priority_and_applies_floor():
    israel = _event("3", "Prime Minister of Israel after the next election?", 39e6, [_market("i", "A", 0.5)])
    feed = {
        "fed-rates": [FED_OCT],
        "economy": [FED_OCT, _event("4", "Largest Company end of December 2026?", 7e6, [_market("n", "NVIDIA", 0.7)]),
                    _event("5", "US recession by end of 2026?", 50_000, [_market("r", "", 0.1)])],
        "elections": [israel, _event("6", "Los Angeles Mayoral Election", 14e6, [_market("l", "X", 0.5)])],
        "geopolitics": [israel, _event("7", "Will China invade Taiwan by end of 2026?", 43e6, [_market("t", "", 0.03)])],
    }
    evs = pm.collect(lambda tag: feed.get(tag, []))
    got = {e["id"]: e["section"] for e in evs}
    assert got == {"1": "central_banks", "3": "elections", "7": "geopolitics"}


def test_outcome_bp():
    assert svc.outcome_bp("25 bps decrease") == (-25, False)
    assert svc.outcome_bp("50+ bps increase") == (50, True)
    assert svc.outcome_bp("No change") == (0, False)
    assert svc.outcome_bp("December 31") is None


def test_fed_compare_matches_next_meeting_and_buckets_futures():
    ev = {**pm.parse_event(FED_OCT), "section": "central_banks"}
    fed = {"meetings": [{"date": "2026-10-28", "distribution": [
        {"change_bp": 0, "prob": 0.4}, {"change_bp": 25, "prob": 0.5}, {"change_bp": 50, "prob": 0.1}]}]}
    cmp = svc.fed_compare([ev], fed)
    rows = {r["label"]: r for r in cmp["rows"]}
    assert rows["25 bps increase"]["polymarket"] == 0.705 and rows["25 bps increase"]["futures"] == 0.5
    assert rows["50+ bps increase"]["futures"] == 0.1 and rows["No change"]["futures"] == 0.4
    assert [r["change_bp"] for r in cmp["rows"]] == sorted(r["change_bp"] for r in cmp["rows"])
    assert svc.fed_compare([ev], {"meetings": [{"date": "2026-12-09", "distribution": []}]}) is None


def test_refresh_stores_snapshot_reuses_history_and_survives_outage():
    ev = {**pm.parse_event(FED_OCT), "section": "central_banks"}
    calls = []

    def hist(tok):
        calls.append(tok)
        return [("2026-09-27", 0.7), ("2026-09-28", 0.705)]

    assert svc.refresh(lambda: [dict(ev)], hist)
    assert svc.refresh(lambda: [dict(ev)], hist)  # second run: history still fresh
    assert calls == ["tokd"]
    snap = svc.snapshot({})
    cb = next(s for s in snap["sections"] if s["id"] == "central_banks")
    assert cb["events"][0]["history"][-1] == ["2026-09-28", 0.705] and snap["error"] is None

    def boom():
        raise RuntimeError("down")
    assert not svc.refresh(boom, hist)
    snap = svc.snapshot({})
    assert snap["error"] == "down" and len(snap["sections"][0]["events"]) == 1  # old snapshot kept


def test_refresh_drops_events_that_left_selection():
    ev = {**pm.parse_event(FED_OCT), "section": "central_banks"}
    svc.refresh(lambda: [ev], lambda t: [])
    svc.refresh(lambda: [], lambda t: [])
    assert db.get_predictions() == []


@respx.mock
def test_fetch_tag_stops_below_volume_floor_and_parses_history():
    route = respx.get(url__startswith=pm.GAMMA).mock(return_value=httpx.Response(
        200, json=[_event(str(i), f"e{i}", 1e6 if i < 99 else 10, []) for i in range(100)]))
    assert len(pm.fetch_tag("fed")) == 100 and route.call_count == 1
    respx.get(url__startswith=pm.CLOB_HISTORY).mock(return_value=httpx.Response(
        200, json={"history": [{"t": 1788048017, "p": 0.7}, {"t": 1788134418, "p": 0.705}]}))
    assert [p for _, p in pm.price_history("tok")] == [0.7, 0.705]


def test_predictions_endpoint(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app
    ev = {**pm.parse_event(FED_OCT), "section": "central_banks"}
    svc.refresh(lambda: [ev], lambda t: [])
    r = TestClient(app).get("/api/predictions")
    assert r.status_code == 200
    body = r.json()
    assert [s["id"] for s in body["sections"]] == ["central_banks", "macro", "elections", "geopolitics"]
    assert body["sections"][0]["events"][0]["title"] == "Fed Decision in October?"
