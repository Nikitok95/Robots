"""Dashboard metric catalog.

Each SeriesDef lists a chain of (adapter, params): the first source that
succeeds is used for that refresh, and every stored value keeps its source label.
"""
from __future__ import annotations

from dataclasses import dataclass, field

GROUPS = [
    ("rates", "Ставки и ожидания"),
    ("spreads", "Спреды США − Япония"),
    ("fx", "Валюты"),
    ("crypto", "Крипто"),
    ("risk", "Риск-аппетит"),
]


@dataclass
class SeriesDef:
    id: str
    name: str
    group: str             # one of GROUPS or "hidden"
    unit: str              # "%", "bp", "USD", "USD bn", "USD m", "BTC", "contracts", "index"
    freq: str              # D, W, M, Q, A
    sources: list[tuple[str, dict]] = field(default_factory=list)
    change: str = "abs"    # bp | pct | abs
    decimals: int = 2
    note: str = ""
    job: str = "markets"   # markets | crypto | macro
    derived: bool = False
    derived_label: str = ""


def S(*a, **kw) -> SeriesDef:
    return SeriesDef(*a, **kw)


SERIES: list[SeriesDef] = [
    # ---------------------------------------------------------------- rates
    S("us2y", "US 2Y", "rates", "%", "D", [("fred", {"series_id": "DGS2"})], "bp"),
    S("us10y", "US 10Y", "rates", "%", "D", [("fred", {"series_id": "DGS10"})], "bp"),
    S("us10y_real", "US 10Y real (TIPS)", "rates", "%", "D", [("fred", {"series_id": "DFII10"})], "bp"),
    S("us2s10s", "Кривая 2s10s", "rates", "%", "D", [("fred", {"series_id": "T10Y2Y"})], "bp"),
    S("us5y5y", "5Y5Y inflation breakeven", "rates", "%", "D", [("fred", {"series_id": "T5YIFR"})], "bp"),
    S("effr", "Effective Fed Funds", "rates", "%", "D", [("fred", {"series_id": "EFFR"})], "bp"),
    S("fed_next_exp_bp", "ФРС: ожидаемое изменение на ближайшем заседании", "rates", "bp", "D",
      change="abs", decimals=1, derived=True,
      derived_label="Расчёт из фьючерсов 30-Day Fed Funds (ZQ, Yahoo) + EFFR (FRED)"),
    S("boj_rate", "Ставка BOJ (O/N call rate)", "rates", "%", "D",
      [("boj", {"db": "FM01", "code": "STRDCLUCON"})], "bp", 3,
      note="Uncollateralized overnight call rate — операционная цель BOJ"),
    S("boj_implied_bp", "BOJ: ожидания на 12М (прокси)", "rates", "bp", "D", change="abs", decimals=0,
      derived=True, derived_label="Расчёт: JGB 1Y (Минфин Японии) − ставка BOJ",
      note="Прокси: бесплатного OIS по TONA нет. Включает срочную премию."),
    S("fed_upper", "Fed target upper", "hidden", "%", "D", [("fred", {"series_id": "DFEDTARU"})], "bp"),
    S("fed_lower", "Fed target lower", "hidden", "%", "D", [("fred", {"series_id": "DFEDTARL"})], "bp"),

    # ---------------------------------------------------------------- spreads
    S("jgb2y", "JGB 2Y", "spreads", "%", "D", [("mof_jgb", {"tenor": "2Y"})], "bp", 3),
    S("jgb10y", "JGB 10Y", "spreads", "%", "D", [("mof_jgb", {"tenor": "10Y"})], "bp", 3),
    S("jgb1y", "JGB 1Y", "hidden", "%", "D", [("mof_jgb", {"tenor": "1Y"})], "bp", 3),
    S("spread_2y", "US2Y − JGB2Y", "spreads", "%", "D", change="bp", derived=True,
      derived_label="Расчёт: FRED DGS2 − Минфин Японии JGB 2Y"),
    S("spread_10y", "US10Y − JGB10Y", "spreads", "%", "D", change="bp", derived=True,
      derived_label="Расчёт: FRED DGS10 − Минфин Японии JGB 10Y"),

    # ---------------------------------------------------------------- fx
    S("usdjpy", "USD/JPY", "fx", "", "D",
      [("yahoo", {"symbol": "JPY=X"}), ("fred", {"series_id": "DEXJPUS"})], "pct", 2),
    S("dxy", "DXY", "fx", "index", "D", [("yahoo", {"symbol": "DX-Y.NYB"})], "pct", 2,
      note="ICE US Dollar Index"),
    S("usdjpy_rv30", "USD/JPY 30D realized vol", "fx", "%", "D", change="abs", derived=True,
      derived_label="Расчёт: 30-дневная реализованная волатильность USD/JPY",
      note="Замена 1M implied vol: бесплатного источника implied vol нет"),
    S("cot_jpy_lev", "CFTC JPY: net leveraged funds", "fx", "contracts", "W",
      [("cftc", {"dataset": "gpe5-46if", "contract_code": "097741"})], "abs", 0,
      note="Лонг − шорт leveraged funds, еженедельно (вторник, публикация в пятницу)"),

    # ---------------------------------------------------------------- crypto
    S("btc", "BTC", "crypto", "USD", "D",
      [("coingecko", {"coin": "bitcoin"}), ("coinbase", {"product": "BTC-USD"})], "pct", 0, job="crypto"),
    S("etf_flow", "Spot BTC ETF: нетто-поток за день", "crypto", "USD m", "D",
      [("sosovalue", {"type": "us-btc-spot"})], "abs", 1, job="crypto"),
    S("etf_flow_5d", "Spot BTC ETF: сумма 5 дней", "crypto", "USD m", "D", change="abs", decimals=1,
      derived=True, derived_label="Расчёт: скользящая сумма 5 торговых дней (SoSoValue)", job="crypto"),
    S("cb_premium", "Coinbase Premium", "crypto", "%", "D", change="abs", decimals=3, derived=True,
      derived_label="Расчёт: (Coinbase BTC-USD − Binance BTCUSDT) / Binance", job="crypto"),
    S("funding", "BTC perp funding (ср. за день)", "crypto", "%", "D",
      [("binance", {"symbol": "BTCUSDT", "metric": "funding"}),
       ("bybit", {"symbol": "BTCUSDT", "metric": "funding"})], "abs", 4, job="crypto",
      note="Среднее 8-часовых ставок за сутки"),
    S("oi", "BTC perp Open Interest", "crypto", "BTC", "D",
      [("bybit", {"symbol": "BTCUSDT", "metric": "oi"}),
       ("binance", {"symbol": "BTCUSDT", "metric": "oi"})], "pct", 0, job="crypto"),
    S("stables", "USDT + USDC капитализация", "crypto", "USD bn", "D",
      [("defillama", {"symbols": ["USDT", "USDC"]})], "pct", 1, job="crypto"),
    S("cb_close", "Coinbase BTC-USD close", "hidden", "USD", "D",
      [("coinbase", {"product": "BTC-USD"})], "pct", 2, job="crypto"),
    S("bn_close", "Binance BTCUSDT close", "hidden", "USD", "D",
      [("binance", {"symbol": "BTCUSDT", "metric": "spot_close"})], "pct", 2, job="crypto"),

    # ---------------------------------------------------------------- risk
    S("vix", "VIX", "risk", "index", "D",
      [("fred", {"series_id": "VIXCLS"}), ("yahoo", {"symbol": "^VIX"})], "abs", 2),
    S("ndx", "Nasdaq 100", "risk", "index", "D",
      [("fred", {"series_id": "NASDAQ100"}), ("yahoo", {"symbol": "^NDX"})], "pct", 0),
    S("brent", "Brent", "risk", "USD", "D",
      [("yahoo", {"symbol": "BZ=F"}), ("fred", {"series_id": "DCOILBRENTEU"})], "pct", 2),
    S("move", "MOVE", "risk", "index", "D", [("yahoo", {"symbol": "^MOVE"})], "abs", 1,
      note="ICE BofA MOVE Index"),
]

BY_ID: dict[str, SeriesDef] = {s.id: s for s in SERIES}

# Spread chart: both spreads + USD/JPY on the second axis
SPREAD_CHART = {"left": ["spread_2y", "spread_10y"], "right": "usdjpy"}
