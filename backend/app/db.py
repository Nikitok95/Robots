"""SQLite storage: observations cache/history, source status, alerts, calendar."""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

from .config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
    series_id  TEXT NOT NULL,
    date       TEXT NOT NULL,          -- YYYY-MM-DD (period end/start for M/Q/A)
    value      REAL NOT NULL,
    source     TEXT NOT NULL,          -- human readable source label
    fetched_at TEXT NOT NULL,          -- ISO UTC
    PRIMARY KEY (series_id, date)
);
CREATE TABLE IF NOT EXISTS series_status (
    series_id    TEXT PRIMARY KEY,
    source       TEXT,
    last_attempt TEXT,
    last_success TEXT,
    last_error   TEXT
);
CREATE TABLE IF NOT EXISTS refresh_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    job         TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    ok          INTEGER,
    failed      INTEGER
);
CREATE TABLE IF NOT EXISTS alert_rules (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT NOT NULL,
    enabled     INTEGER NOT NULL DEFAULT 1,
    params      TEXT NOT NULL          -- JSON
);
CREATE TABLE IF NOT EXISTS alert_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id      TEXT NOT NULL,
    date         TEXT NOT NULL,
    triggered_at TEXT NOT NULL,
    message      TEXT NOT NULL,
    details      TEXT NOT NULL,
    UNIQUE (rule_id, date)
);
CREATE TABLE IF NOT EXISTS calendar_events (
    id         TEXT PRIMARY KEY,
    currency   TEXT,
    country    TEXT,
    ts         TEXT NOT NULL,          -- ISO UTC
    title      TEXT NOT NULL,
    impact     TEXT,
    actual     TEXT,
    forecast   TEXT,
    previous   TEXT,
    source     TEXT NOT NULL,
    fetched_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cal_ts ON calendar_events (ts);
"""

_local = threading.local()
_write_lock = threading.Lock()


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _path() -> str:
    return get_settings().db_path


def connect() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    path = _path()
    if conn is None or getattr(_local, "path", None) != path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, check_same_thread=False, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        _local.conn, _local.path = conn, path
    return conn


@contextmanager
def tx() -> Iterator[sqlite3.Connection]:
    conn = connect()
    with _write_lock:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def init_db() -> None:
    with tx() as c:
        c.executescript(SCHEMA)


def reset_connection() -> None:
    conn = getattr(_local, "conn", None)
    if conn is not None:
        conn.close()
    _local.conn = None
    _local.path = None


# ---------------------------------------------------------------- observations
def upsert_observations(series_id: str, rows: Iterable[tuple[str, float]], source: str) -> int:
    now = utcnow_iso()
    data = [(series_id, d, float(v), source, now) for d, v in rows]
    if not data:
        return 0
    with tx() as c:
        c.executemany(
            """INSERT INTO observations (series_id, date, value, source, fetched_at)
               VALUES (?,?,?,?,?)
               ON CONFLICT(series_id, date) DO UPDATE SET
                 value=excluded.value, source=excluded.source, fetched_at=excluded.fetched_at
               WHERE observations.value != excluded.value OR observations.source != excluded.source""",
            data,
        )
    return len(data)


def last_date(series_id: str) -> str | None:
    r = connect().execute("SELECT MAX(date) d FROM observations WHERE series_id=?", (series_id,)).fetchone()
    return r["d"] if r else None


def get_series(series_id: str, start: str | None = None) -> list[sqlite3.Row]:
    q = "SELECT date, value, source, fetched_at FROM observations WHERE series_id=?"
    args: list = [series_id]
    if start:
        q += " AND date>=?"
        args.append(start)
    return connect().execute(q + " ORDER BY date", args).fetchall()


def get_series_ids(prefix: str) -> list[str]:
    rows = connect().execute(
        "SELECT DISTINCT series_id FROM observations WHERE series_id LIKE ?", (prefix + "%",)
    ).fetchall()
    return [r["series_id"] for r in rows]


# ---------------------------------------------------------------- status
def set_status(series_id: str, source: str, error: str | None) -> None:
    now = utcnow_iso()
    with tx() as c:
        if error is None:
            c.execute(
                """INSERT INTO series_status (series_id, source, last_attempt, last_success, last_error)
                   VALUES (?,?,?,?,NULL)
                   ON CONFLICT(series_id) DO UPDATE SET source=excluded.source,
                     last_attempt=excluded.last_attempt, last_success=excluded.last_success, last_error=NULL""",
                (series_id, source, now, now),
            )
        else:
            c.execute(
                """INSERT INTO series_status (series_id, source, last_attempt, last_error)
                   VALUES (?,?,?,?)
                   ON CONFLICT(series_id) DO UPDATE SET
                     last_attempt=excluded.last_attempt, last_error=excluded.last_error""",
                (series_id, source, now, error[:500]),
            )


def get_status(series_id: str) -> sqlite3.Row | None:
    return connect().execute("SELECT * FROM series_status WHERE series_id=?", (series_id,)).fetchone()


def all_status() -> list[sqlite3.Row]:
    return connect().execute("SELECT * FROM series_status ORDER BY series_id").fetchall()


# ---------------------------------------------------------------- refresh log
def log_refresh_start(job: str) -> int:
    with tx() as c:
        cur = c.execute("INSERT INTO refresh_log (job, started_at) VALUES (?,?)", (job, utcnow_iso()))
        return int(cur.lastrowid)


def log_refresh_end(log_id: int, ok: int, failed: int) -> None:
    with tx() as c:
        c.execute(
            "UPDATE refresh_log SET finished_at=?, ok=?, failed=? WHERE id=?",
            (utcnow_iso(), ok, failed, log_id),
        )


def last_refresh() -> sqlite3.Row | None:
    return connect().execute(
        "SELECT * FROM refresh_log WHERE finished_at IS NOT NULL ORDER BY finished_at DESC LIMIT 1"
    ).fetchone()


# ---------------------------------------------------------------- alerts
def get_rules() -> list[dict]:
    rows = connect().execute("SELECT * FROM alert_rules ORDER BY id").fetchall()
    return [
        {**dict(r), "enabled": bool(r["enabled"]), "params": json.loads(r["params"])} for r in rows
    ]


def seed_rule(rule_id: str, name: str, description: str, params: dict) -> None:
    with tx() as c:
        c.execute(
            "INSERT OR IGNORE INTO alert_rules (id, name, description, enabled, params) VALUES (?,?,?,1,?)",
            (rule_id, name, description, json.dumps(params)),
        )


def update_rule(rule_id: str, enabled: bool | None, params: dict | None) -> None:
    with tx() as c:
        if enabled is not None:
            c.execute("UPDATE alert_rules SET enabled=? WHERE id=?", (int(enabled), rule_id))
        if params is not None:
            c.execute("UPDATE alert_rules SET params=? WHERE id=?", (json.dumps(params), rule_id))


def insert_alert_event(rule_id: str, date: str, message: str, details: dict) -> bool:
    with tx() as c:
        cur = c.execute(
            "INSERT OR IGNORE INTO alert_events (rule_id, date, triggered_at, message, details) VALUES (?,?,?,?,?)",
            (rule_id, date, utcnow_iso(), message, json.dumps(details)),
        )
        return cur.rowcount > 0


def get_alert_events(limit: int = 100) -> list[dict]:
    rows = connect().execute(
        "SELECT * FROM alert_events ORDER BY date DESC, id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [{**dict(r), "details": json.loads(r["details"])} for r in rows]


# ---------------------------------------------------------------- calendar
def upsert_calendar(events: list[dict], source: str) -> int:
    now = utcnow_iso()
    with tx() as c:
        c.executemany(
            """INSERT INTO calendar_events (id, currency, country, ts, title, impact, actual, forecast, previous, source, fetched_at)
               VALUES (:id,:currency,:country,:ts,:title,:impact,:actual,:forecast,:previous,:source,:fetched_at)
               ON CONFLICT(id) DO UPDATE SET ts=excluded.ts, impact=excluded.impact, actual=excluded.actual,
                 forecast=excluded.forecast, previous=excluded.previous, fetched_at=excluded.fetched_at""",
            [{**e, "source": source, "fetched_at": now} for e in events],
        )
    return len(events)


def get_calendar(start_iso: str, end_iso: str, currencies: list[str] | None = None,
                 countries: list[str] | None = None) -> list[dict]:
    q = "SELECT * FROM calendar_events WHERE ts>=? AND ts<?"
    args: list = [start_iso, end_iso]
    conds = []
    if currencies:
        conds.append(f"currency IN ({','.join('?' * len(currencies))})")
        args += currencies
    if countries:
        conds.append(f"country IN ({','.join('?' * len(countries))})")
        args += countries
    if conds:
        q += " AND (" + " OR ".join(conds) + ")"
    return [dict(r) for r in connect().execute(q + " ORDER BY ts", args).fetchall()]
