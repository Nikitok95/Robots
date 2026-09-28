from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    db_path: str = str(BASE_DIR / "data" / "macro.db")
    timezone: str = "Europe/Madrid"

    # Keys (only on backend)
    fred_api_key: str = ""
    sosovalue_api_key: str = ""
    coingecko_api_key: str = ""  # optional demo key
    tradingeconomics_api_key: str = ""
    fmp_api_key: str = ""

    # SoSoValue endpoint is configurable: the public docs moved between versions.
    sosovalue_etf_url: str = "https://api.sosovalue.xyz/openapi/v2/etf/historicalInflowChart"

    # Schedules (cron in Europe/Madrid)
    refresh_cron_markets: str = "30 7,23 * * *"
    refresh_cron_crypto: str = "5 * * * *"
    refresh_cron_macro: str = "0 6 * * *"
    refresh_cron_predictions: str = "20 * * * *"
    scheduler_enabled: bool = True
    refresh_on_startup: bool = True

    http_timeout: float = 30.0
    backfill_years: int = 6


@lru_cache
def get_settings() -> Settings:
    return Settings()
