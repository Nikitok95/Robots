"""DefiLlama stablecoins API (no key). Sums circulating USD of the given
symbols (USDT + USDC). Asset ids are resolved by symbol, not hardcoded."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone

from .base import Obs, SourceAdapter, SourceError, http

LIST_URL = "https://stablecoins.llama.fi/stablecoins"
CHART_URL = "https://stablecoins.llama.fi/stablecoincharts/all"


class DefiLlamaAdapter(SourceAdapter):
    name = "defillama"
    label = "DefiLlama"
    homepage = "https://defillama.com/stablecoins"

    def source_label(self, params: dict) -> str:
        return f"{self.label} · {'+'.join(params['symbols'])}"

    def resolve_ids(self, symbols: list[str]) -> dict[str, str]:
        assets = http.get(LIST_URL).json().get("peggedAssets") or []
        ids: dict[str, str] = {}
        for sym in symbols:
            cands = [a for a in assets if str(a.get("symbol", "")).upper() == sym.upper()]
            if not cands:
                raise SourceError(f"DefiLlama: не найден стейблкоин {sym}")
            # pick the largest if several share a symbol
            best = max(cands, key=lambda a: float((a.get("circulating") or {}).get("peggedUSD") or 0))
            ids[sym] = str(best["id"])
        return ids

    def fetch(self, params: dict, since: date | None) -> list[Obs]:
        total: dict[str, float] = defaultdict(float)
        counts: dict[str, int] = defaultdict(int)
        ids = self.resolve_ids(params["symbols"])
        for sym, sid in ids.items():
            rows = http.get(CHART_URL, params={"stablecoin": sid}).json()
            if not isinstance(rows, list):
                raise SourceError(f"DefiLlama {sym}: {str(rows)[:200]}")
            for r in rows:
                d = datetime.fromtimestamp(int(r["date"]), tz=timezone.utc).date().isoformat()
                v = (r.get("totalCirculatingUSD") or {}).get("peggedUSD")
                if v is None:
                    continue
                total[d] += float(v) / 1e9
                counts[d] += 1
        n = len(ids)
        out = [Obs(d, v) for d, v in sorted(total.items()) if counts[d] == n]
        if since:
            out = [o for o in out if o.date >= since.isoformat()]
        return out
