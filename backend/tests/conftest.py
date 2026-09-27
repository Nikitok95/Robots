import os

import pytest


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    monkeypatch.setenv("REFRESH_ON_STARTUP", "false")
    monkeypatch.setenv("FRED_API_KEY", "test-key")
    monkeypatch.setenv("SOSOVALUE_API_KEY", "soso-key")
    for k in ("TRADINGECONOMICS_API_KEY", "FMP_API_KEY", "COINGECKO_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    from app import db
    from app.adapters import http
    from app.config import get_settings
    get_settings.cache_clear()
    db.reset_connection()
    http.clear_cache()
    db.init_db()
    yield
    db.reset_connection()
    get_settings.cache_clear()
