import logging
import threading
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel

from . import db, scheduler, views
from .alerts import RULES_BY_ID, evaluate_all, rules_with_state, seed_rules
from .config import get_settings
from .ingest import fed_snapshot, run_job, running

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    seed_rules()
    s = get_settings()
    if s.scheduler_enabled:
        scheduler.start()
    if s.refresh_on_startup:
        threading.Thread(target=run_job, args=("all",), daemon=True).start()
    yield
    scheduler.stop()


app = FastAPI(title="Macro Dashboard API", lifespan=lifespan)


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/dashboard")
def dashboard():
    return views.dashboard()


@app.get("/api/series/{series_id}")
def series(series_id: str, period: str = "1Y"):
    return views.series_chart(series_id, period)


@app.get("/api/charts/spreads")
def spreads(period: str = "1Y"):
    return views.spread_chart(period)


@app.get("/api/fed")
def fed():
    return fed_snapshot()


@app.post("/api/refresh")
def refresh(bg: BackgroundTasks, job: str = "all", force: bool = True):
    if job not in ("all", "markets", "crypto", "macro"):
        raise HTTPException(400, "job must be all|markets|crypto|macro")
    # macro data are annual/monthly: a manual refresh respects their min interval
    bg.add_task(run_job, job, force and job != "macro")
    return {"started": job}


@app.get("/api/status")
def status():
    lr = db.last_refresh()
    return {"last_refresh": dict(lr) if lr else None, "running": {k: v for k, v in running.items() if v},
            "next_runs": scheduler.next_runs(), "timezone": get_settings().timezone}


@app.get("/api/sources")
def sources():
    return views.sources()


# ------------------------------------------------------------------ alerts
class RuleUpdate(BaseModel):
    enabled: bool | None = None
    params: dict | None = None


@app.get("/api/alerts/rules")
def alert_rules():
    return rules_with_state()


@app.put("/api/alerts/rules/{rule_id}")
def update_alert_rule(rule_id: str, body: RuleUpdate):
    rd = RULES_BY_ID.get(rule_id)
    if not rd:
        raise HTTPException(404, "unknown rule")
    params = None
    if body.params is not None:
        params = {}
        for k, default in rd.defaults.items():
            v = body.params.get(k, default)
            try:
                params[k] = type(default)(v) if not isinstance(default, int) or isinstance(v, int) else float(v)
            except (TypeError, ValueError):
                raise HTTPException(400, f"bad value for {k}")
    db.update_rule(rule_id, body.enabled, params)
    evaluate_all()
    return next(r for r in rules_with_state() if r["id"] == rule_id)


@app.get("/api/alerts/events")
def alert_events(limit: int = 100):
    return db.get_alert_events(limit)


# ------------------------------------------------------------------ map
@app.get("/api/map")
def world_map():
    return views.map_summary()


@app.get("/api/map/country/{code}")
def country(code: str):
    res = views.country_detail(code.upper())
    if res is None:
        raise HTTPException(404, "unknown country")
    return res
