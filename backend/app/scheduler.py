import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import get_settings
from .ingest import run_job

log = logging.getLogger(__name__)
_sched: BackgroundScheduler | None = None


def start() -> BackgroundScheduler:
    global _sched
    s = get_settings()
    _sched = BackgroundScheduler(timezone=s.timezone)
    for job, cron in (("markets", s.refresh_cron_markets), ("crypto", s.refresh_cron_crypto),
                      ("macro", s.refresh_cron_macro), ("predictions", s.refresh_cron_predictions)):
        _sched.add_job(run_job, CronTrigger.from_crontab(cron, timezone=s.timezone), args=[job],
                       id=job, max_instances=1, coalesce=True, misfire_grace_time=3600)
    _sched.start()
    log.info("scheduler started (%s)", s.timezone)
    return _sched


def stop() -> None:
    if _sched:
        _sched.shutdown(wait=False)


def next_runs() -> dict:
    if not _sched:
        return {}
    return {j.id: j.next_run_time.isoformat() if j.next_run_time else None for j in _sched.get_jobs()}
