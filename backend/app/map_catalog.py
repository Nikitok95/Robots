"""World-map country indicators. Series ids: c.<CODE>.<indicator>.
Source chains are templates filled with each country's codes from countries.yaml."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import yaml

from .config import CONFIG_DIR

KEI = {"agency": "OECD.SDD.STES", "flow": "DSD_KEI@DF_KEI"}
QNA = {"agency": "OECD.SDD.NAD", "flow": "DSD_NAMAIN1@DF_QNA_EXPENDITURE_GROWTH_OECD"}
PRICES = {"agency": "OECD.SDD.TPS", "flow": "DSD_PRICES@DF_PRICES_ALL"}


@dataclass
class Indicator:
    id: str
    name: str
    tab: str          # macro | budget | micro | overview
    unit: str
    freq: str
    decimals: int = 1
    note: str = ""


INDICATORS: list[Indicator] = [
    Indicator("fx", "Курс к USD", "overview", "", "D", 4),
    Indicator("policy_rate", "Ставка ЦБ", "macro", "%", "D", 2),
    Indicator("cpi_yoy", "CPI, г/г", "macro", "%", "M"),
    Indicator("core_cpi_yoy", "Core CPI, г/г", "macro", "%", "M"),
    Indicator("y10", "Доходность 10Y", "macro", "%", "M", 2),
    Indicator("gdp_qoq", "ВВП, к/к", "macro", "%", "Q"),
    Indicator("gdp_yoy", "ВВП, г/г", "macro", "%", "Q"),
    Indicator("gdp_annual", "Рост ВВП (годовой, IMF WEO)", "macro", "%", "A"),
    Indicator("unemployment", "Безработица", "macro", "%", "M"),
    Indicator("current_account", "Счёт текущих операций, % ВВП", "macro", "% ВВП", "A"),
    Indicator("trade_balance", "Торговый баланс (товары и услуги), % ВВП", "macro", "% ВВП", "A"),
    Indicator("budget_balance", "Бюджет: профицит (+) / дефицит (−), % ВВП", "budget", "% ВВП", "A"),
    Indicator("gov_debt", "Госдолг, % ВВП", "budget", "% ВВП", "A"),
    Indicator("gov_revenue", "Доходы бюджета, % ВВП", "budget", "% ВВП", "A"),
    Indicator("gov_expenditure", "Расходы бюджета, % ВВП", "budget", "% ВВП", "A"),
    Indicator("pmi_manuf", "PMI производства", "micro", "", "M"),
    Indicator("pmi_services", "PMI услуг", "micro", "", "M"),
    Indicator("business_conf", "Деловое доверие (OECD BCI, прокси PMI)", "micro", "", "M",
              note="Бесплатная замена PMI: OECD Business Confidence Indicator, 100 = норма"),
    Indicator("retail_yoy", "Розничные продажи (объём), г/г", "micro", "%", "M"),
    Indicator("indprod_yoy", "Промпроизводство, г/г", "micro", "%", "M"),
    Indicator("cons_conf", "Потребительское доверие (OECD CCI)", "micro", "", "M"),
    Indicator("wages_yoy", "Рост зарплат, г/г", "micro", "%", "M"),
    Indicator("house_prices_yoy", "Цены на жильё (реальные), г/г", "micro", "%", "Q"),
]
IND_BY_ID = {i.id: i for i in INDICATORS}

# Indicators that come from the euro-area aggregate for members
EA_ONLY = {"fx", "policy_rate"}


def _kei(c: dict, measure: str, prefer_extra: list[dict]) -> tuple[str, dict] | None:
    if not c.get("oecd"):
        return None
    return ("oecd", {**KEI, "dims": {"REF_AREA": c["oecd"], "FREQ": "M"},
                     "prefer": [{"MEASURE": measure, **p} for p in prefer_extra]})


def source_chain(ind: str, c: dict) -> list[tuple[str, dict]]:
    """Candidate sources for indicator `ind` of country `c` (first success wins)."""
    ch: list = []
    code = c["code"]
    if ind == "fx":
        if c.get("currency") and c["currency"] != "USD":
            ch.append(("frankfurter", {"currency": c["currency"]}))
    elif ind == "policy_rate":
        if c.get("bis") and code != "SG":
            ch += [("bis", {"flow": "WS_CBPOL", "key": f"D.{c['bis']}"}),
                   ("bis", {"flow": "WS_CBPOL", "key": f"M.{c['bis']}"})]
    elif ind == "cpi_yoy":
        if c.get("bis"):
            ch.append(("bis", {"flow": "WS_LONG_CPI", "key": f"M.{c['bis']}.771"}))
        if c.get("oecd"):
            ch.append(("oecd", {**PRICES, "dims": {"REF_AREA": c["oecd"], "FREQ": "M"},
                                "prefer": [{"MEASURE": "CPI", "EXPENDITURE": "_T", "TRANSFORMATION": "GY"}]}))
    elif ind == "core_cpi_yoy":
        if c.get("oecd"):
            ch.append(("oecd", {**PRICES, "dims": {"REF_AREA": c["oecd"], "FREQ": "M"},
                                "prefer": [{"MEASURE": "CPI", "EXPENDITURE": "_TXCP01_NRG", "TRANSFORMATION": "GY"}]}))
    elif ind == "y10":
        if code == "US":
            ch.append(("alias", {"series": "us10y"}))
        elif code == "JP":
            ch.append(("alias", {"series": "jgb10y"}))
        k = _kei(c, "IRLT", [{}])
        if k:
            ch.append(k)
    elif ind in ("gdp_qoq", "gdp_yoy"):
        if c.get("oecd"):
            tr = "G1" if ind == "gdp_qoq" else "GY"
            ch.append(("oecd", {**QNA, "dims": {"REF_AREA": c["oecd"], "FREQ": "Q"},
                                "prefer": [{"TRANSACTION": "B1GQ", "TRANSFORMATION": tr, "ADJUSTMENT": "Y"},
                                           {"TRANSACTION": "B1GQ", "TRANSFORMATION": tr}]}))
    elif ind == "gdp_annual":
        ch.append(("imf", {"indicator": "NGDP_RPCH", "code": c.get("imf")}))
    elif ind == "unemployment":
        k = _kei(c, "UNEMP", [{"ADJUSTMENT": "Y"}, {}])
        if k:
            ch.append(k)
        ch.append(("imf", {"indicator": "LUR", "code": c.get("imf")}))
    elif ind == "current_account":
        ch.append(("imf", {"indicator": "BCA_NGDPD", "code": c.get("imf")}))
    elif ind == "trade_balance":
        ch.append(("worldbank", {"indicator": "NE.RSB.GNFS.ZS", "code": c.get("wb")}))
    elif ind == "budget_balance":
        ch.append(("imf", {"indicator": "GGXCNL_NGDP", "code": c.get("imf")}))
    elif ind == "gov_debt":
        ch.append(("imf", {"indicator": "GGXWDG_NGDP", "code": c.get("imf")}))
    elif ind == "gov_revenue":
        ch.append(("imf", {"indicator": "GGR_NGDP", "code": c.get("imf")}))
    elif ind == "gov_expenditure":
        ch.append(("imf", {"indicator": "GGX_NGDP", "code": c.get("imf")}))
    elif ind == "pmi_manuf":
        if c.get("te"):
            ch.append(("tradingeconomics", {"country": c["te"], "indicator": "Manufacturing PMI"}))
    elif ind == "pmi_services":
        if c.get("te"):
            ch.append(("tradingeconomics", {"country": c["te"], "indicator": "Services PMI"}))
    elif ind == "business_conf":
        k = _kei(c, "BCICP", [{}])
        if k:
            ch.append(k)
    elif ind == "retail_yoy":
        k = _kei(c, "TOVM", [{"TRANSFORMATION": "GY"}])
        if k:
            ch.append(k)
    elif ind == "indprod_yoy":
        k = _kei(c, "PRVM", [{"TRANSFORMATION": "GY"}])
        if k:
            ch.append(k)
    elif ind == "cons_conf":
        k = _kei(c, "CCICP", [{}])
        if k:
            ch.append(k)
    elif ind == "wages_yoy":
        if c.get("te"):
            ch.append(("tradingeconomics", {"country": c["te"], "indicator": "Wage Growth"}))
    elif ind == "house_prices_yoy":
        if c.get("bis"):
            ch.append(("bis", {"flow": "WS_SPP", "key": f"Q.{c['bis']}.R.771"}))
    return [(a, p) for a, p in ch if all(v is not None for v in p.values())]


@lru_cache
def load_countries() -> dict:
    with open(CONFIG_DIR / "countries.yaml", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    for m in data.get("eurozone", []):
        m.setdefault("currency", "EUR")
        m.setdefault("group", "EUR")
        m["member_of"] = "EA"
    return data


@lru_cache
def load_cb_meetings() -> dict:
    with open(CONFIG_DIR / "cb_meetings.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def all_entities() -> list[dict]:
    d = load_countries()
    return d["countries"] + d.get("eurozone", [])


def entity(code: str) -> dict | None:
    return next((c for c in all_entities() if c["code"] == code), None)


def series_id(code: str, ind: str) -> str:
    return f"c.{code}.{ind}"


def country_jobs() -> list[tuple[str, Indicator, list]]:
    """(series_id, indicator, source chain) for every country/indicator to fetch."""
    jobs = []
    for c in all_entities():
        member = c.get("member_of")
        if member and not c.get("detail"):
            inds = ["gdp_annual", "budget_balance", "gov_debt", "current_account"]
        else:
            inds = [i.id for i in INDICATORS]
        for ind in inds:
            if member and ind in EA_ONLY:
                continue
            chain = source_chain(ind, c)
            if chain:
                jobs.append((series_id(c["code"], ind), IND_BY_ID[ind], chain))
    return jobs
