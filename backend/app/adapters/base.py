"""Common adapter interface.

Every data source is one class implementing `SourceAdapter.fetch(params, since)`
and returning a list of `Obs(date, value)`. Calendar sources implement
`CalendarAdapter.fetch_events(start, end)`.
"""
from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx

from ..config import get_settings

log = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36 macro-dashboard/1.0"
)


@dataclass(frozen=True)
class Obs:
    date: str  # YYYY-MM-DD
    value: float


class SourceError(Exception):
    """Raised when a source is unreachable or returns unexpected data."""


class MissingKeyError(SourceError):
    pass


class _Http:
    """Shared HTTP client with retries and a short in-memory GET cache
    (one refresh run often reads the same CSV/JSON for several series)."""

    CACHE_TTL = 600

    def __init__(self) -> None:
        self._client: httpx.Client | None = None
        self._cache: dict[str, tuple[float, httpx.Response]] = {}
        self._lock = threading.Lock()

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                timeout=get_settings().http_timeout,
                headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
                follow_redirects=True,
            )
        return self._client

    def request(self, method: str, url: str, *, params: dict | None = None, headers: dict | None = None,
                json: Any = None, cache: bool = True, retries: int = 3) -> httpx.Response:
        key = f"{method} {url} {sorted((params or {}).items())} {json}"
        if cache:
            with self._lock:
                hit = self._cache.get(key)
            if hit and time.time() - hit[0] < self.CACHE_TTL:
                return hit[1]
        last_exc: Exception | None = None
        for attempt in range(retries):
            try:
                r = self.client.request(method, url, params=params, headers=headers, json=json)
                if r.status_code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                if r.status_code >= 400:
                    raise SourceError(f"HTTP {r.status_code} from {r.request.url.host}: {r.text[:200]}")
                if cache:
                    with self._lock:
                        self._cache[key] = (time.time(), r)
                return r
            except httpx.HTTPError as e:
                last_exc = e
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
        raise SourceError(f"{type(last_exc).__name__}: {last_exc} ({url})")

    def get(self, url: str, **kw) -> httpx.Response:
        return self.request("GET", url, **kw)

    def clear_cache(self) -> None:
        with self._lock:
            self._cache.clear()


http = _Http()


class SourceAdapter(ABC):
    #: registry key, e.g. "fred"
    name: str = ""
    #: short human label shown next to values
    label: str = ""
    #: settings attribute holding the API key, if the source needs one
    key_setting: str | None = None
    #: docs / homepage for the source list in the UI
    homepage: str = ""

    def api_key(self) -> str:
        if not self.key_setting:
            return ""
        return getattr(get_settings(), self.key_setting, "") or ""

    def available(self) -> bool:
        return not self.key_setting or bool(self.api_key())

    def require_key(self) -> str:
        k = self.api_key()
        if not k:
            raise MissingKeyError(f"{self.label}: не задан ключ {self.key_setting.upper()} в .env")
        return k

    def source_label(self, params: dict) -> str:
        ident = params.get("series_id") or params.get("symbol") or params.get("code") or ""
        return f"{self.label} · {ident}" if ident else self.label

    @abstractmethod
    def fetch(self, params: dict, since: date | None) -> list[Obs]:
        ...


class CalendarAdapter(ABC):
    name: str = ""
    label: str = ""
    key_setting: str | None = None

    def available(self) -> bool:
        return not self.key_setting or bool(getattr(get_settings(), self.key_setting, ""))

    @abstractmethod
    def fetch_events(self, start: date, end: date) -> list[dict]:
        """Return dicts with keys: id, currency, country, ts (ISO UTC), title,
        impact, actual, forecast, previous."""


def to_float(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", "")
    if s in ("", ".", "-", "NaN", "nan", "N/A", "NA", "null"):
        return None
    try:
        return float(s)
    except ValueError:
        return None
