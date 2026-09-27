"""Adapter tests on recorded-format fixtures (no network)."""
import json
from datetime import date

import httpx
import pytest
import respx

from app.adapters import ADAPTERS, SourceError
from app.adapters.forexfactory import parse as ff_parse
from app.adapters.mof_jgb import parse_csv as mof_parse, parse_date as mof_date
from app.adapters.oecd import parse_dimensions, select_series
from app.adapters.sosovalue import parse as soso_parse


@respx.mock
def test_fred_skips_missing_values():
    route = respx.get("https://api.stlouisfed.org/fred/series/observations").mock(
        return_value=httpx.Response(200, json={"observations": [
            {"date": "2026-09-17", "value": "3.61"}, {"date": "2026-09-18", "value": "."},
            {"date": "2026-09-21", "value": "3.58"}]}))
    obs = ADAPTERS["fred"].fetch({"series_id": "DGS2"}, date(2026, 9, 1))
    assert [(o.date, o.value) for o in obs] == [("2026-09-17", 3.61), ("2026-09-21", 3.58)]
    q = route.calls[0].request.url.params
    assert q["series_id"] == "DGS2" and q["api_key"] == "test-key" and q["observation_start"] == "2026-09-01"


@respx.mock
def test_fred_error_payload():
    respx.get("https://api.stlouisfed.org/fred/series/observations").mock(
        return_value=httpx.Response(400, json={"error_code": 400, "error_message": "Bad Request. The value for variable api_key is not registered."}))
    with pytest.raises(SourceError):
        ADAPTERS["fred"].fetch({"series_id": "DGS2"}, None)


def test_fred_missing_key(monkeypatch):
    from app.adapters import MissingKeyError
    from app.config import get_settings
    monkeypatch.setenv("FRED_API_KEY", "")
    get_settings.cache_clear()
    with pytest.raises(MissingKeyError):
        ADAPTERS["fred"].fetch({"series_id": "DGS2"}, None)


@respx.mock
def test_yahoo_chart():
    respx.get(url__regex=r"https://query1\.finance\.yahoo\.com/v8/finance/chart/JPY=X.*").mock(
        return_value=httpx.Response(200, json={"chart": {"error": None, "result": [{
            "meta": {"gmtoffset": 3600},
            "timestamp": [1758495600, 1758582000, 1758668400],
            "indicators": {"quote": [{"close": [147.8, None, 148.25]}]}}]}}))
    obs = ADAPTERS["yahoo"].fetch({"symbol": "JPY=X"}, date(2025, 9, 1))
    assert [o.value for o in obs] == [147.8, 148.25]
    assert obs[0].date == "2025-09-22"


@respx.mock
def test_yahoo_error():
    respx.get(url__regex=r".*chart/ZQX26\.CBT.*").mock(return_value=httpx.Response(
        200, json={"chart": {"result": None, "error": {"code": "Not Found", "description": "No data found"}}}))
    with pytest.raises(SourceError):
        ADAPTERS["yahoo"].fetch({"symbol": "ZQX26.CBT"}, None)


MOF_CSV = """Interest Rate,,,,,,,,,,,,,,,
Date,1Y,2Y,3Y,4Y,5Y,6Y,7Y,8Y,9Y,10Y,15Y,20Y,25Y,30Y,40Y
2026/9/18,0.812,0.955,1.05,1.12,1.2,1.29,1.38,1.47,1.56,1.65,2.1,2.5,2.7,2.85,3.0
2026/9/19,0.815,-,1.06,1.13,1.21,1.3,1.39,1.48,1.57,1.66,2.11,2.51,2.71,2.86,3.01
"""


def test_mof_csv_parsing():
    obs = mof_parse(MOF_CSV, "2Y")
    assert [(o.date, o.value) for o in obs] == [("2026-09-18", 0.955)]
    assert mof_parse(MOF_CSV, "10Y")[-1].value == 1.66
    assert mof_date("S49.9.24") == "1974-09-24"
    assert mof_date("R8.9.22") == "2026-09-22"
    with pytest.raises(SourceError):
        mof_parse(MOF_CSV, "3M")


@respx.mock
def test_mof_adapter_shift_jis_current_month_only():
    respx.get("https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/jgbcme.csv").mock(
        return_value=httpx.Response(200, content=("国債金利情報\n" + MOF_CSV.split("\n", 1)[1]).encode("cp932")))
    since = date.today().replace(day=1)
    obs = ADAPTERS["mof_jgb"].fetch({"tenor": "10Y"}, since)
    assert all(o.date >= since.isoformat() for o in obs)


@respx.mock
def test_boj():
    respx.get("https://www.stat-search.boj.or.jp/api/v1/getDataCode").mock(return_value=httpx.Response(200, json={
        "STATUS": 200, "MESSAGE": "OK", "NEXTPOSITION": None,
        "RESULTSET": [{"SERIES_CODE": "STRDCLUCON", "VALUES": {
            "SURVEY_DATES": ["20260918", "20260919"], "VALUES": [0.727, None]}}]}))
    obs = ADAPTERS["boj"].fetch({"db": "FM01", "code": "STRDCLUCON"}, date(2026, 9, 1))
    assert [(o.date, o.value) for o in obs] == [("2026-09-18", 0.727)]


@respx.mock
def test_coingecko_daily_last_point_wins():
    respx.get("https://api.coingecko.com/api/v3/coins/bitcoin/market_chart").mock(return_value=httpx.Response(
        200, json={"prices": [[1758499200000, 115000.0], [1758585600000, 116000.0], [1758620000000, 116500.0]]}))
    obs = ADAPTERS["coingecko"].fetch({"coin": "bitcoin"}, None)
    assert obs[-1].value == 116500.0 and len(obs) == 2


@respx.mock
def test_coinbase_candles():
    respx.get("https://api.exchange.coinbase.com/products/BTC-USD/candles").mock(return_value=httpx.Response(
        200, json=[[1758585600, 1, 2, 1.5, 116100.5, 10], [1758499200, 1, 2, 1.5, 115050.0, 10]]))
    obs = ADAPTERS["coinbase"].fetch({"product": "BTC-USD"}, date.today())
    assert [o.value for o in obs] == [115050.0, 116100.5]


@respx.mock
def test_binance_funding_daily_mean_percent():
    respx.get("https://fapi.binance.com/fapi/v1/fundingRate").mock(return_value=httpx.Response(200, json=[
        {"symbol": "BTCUSDT", "fundingTime": 1758499200000, "fundingRate": "0.00010000"},
        {"symbol": "BTCUSDT", "fundingTime": 1758528000000, "fundingRate": "0.00005000"},
        {"symbol": "BTCUSDT", "fundingTime": 1758585600000, "fundingRate": "-0.00002000"}]))
    obs = ADAPTERS["binance"].fetch({"symbol": "BTCUSDT", "metric": "funding"}, date(2025, 9, 1))
    assert obs[0].value == pytest.approx(0.0075)
    assert obs[1].value == pytest.approx(-0.002)


@respx.mock
def test_binance_spot_falls_back_to_mirror():
    respx.get("https://api.binance.com/api/v3/klines").mock(return_value=httpx.Response(451, json={"msg": "restricted"}))
    respx.get("https://data-api.binance.vision/api/v3/klines").mock(return_value=httpx.Response(
        200, json=[[1758499200000, "1", "2", "0.5", "115020.1", "100"]]))
    obs = ADAPTERS["binance"].fetch({"symbol": "BTCUSDT", "metric": "spot_close"}, date(2025, 9, 1))
    assert obs == [type(obs[0])("2025-09-22", 115020.1)]


@respx.mock
def test_binance_oi():
    respx.get("https://fapi.binance.com/futures/data/openInterestHist").mock(return_value=httpx.Response(200, json=[
        {"symbol": "BTCUSDT", "sumOpenInterest": "80000.5", "sumOpenInterestValue": "9.2e9", "timestamp": 1758499200000}]))
    obs = ADAPTERS["binance"].fetch({"symbol": "BTCUSDT", "metric": "oi"}, None)
    assert obs[0].value == 80000.5


@respx.mock
def test_bybit_oi_and_error():
    respx.get("https://api.bybit.com/v5/market/open-interest").mock(return_value=httpx.Response(200, json={
        "retCode": 0, "retMsg": "OK", "result": {"list": [
            {"openInterest": "51000.1", "timestamp": "1758585600000"},
            {"openInterest": "50000.0", "timestamp": "1758499200000"}], "nextPageCursor": ""}}))
    obs = ADAPTERS["bybit"].fetch({"symbol": "BTCUSDT", "metric": "oi"}, date(2025, 9, 1))
    assert [o.value for o in obs] == [50000.0, 51000.1]
    respx.get("https://api.bybit.com/v5/market/funding/history").mock(return_value=httpx.Response(
        200, json={"retCode": 10001, "retMsg": "params error", "result": {}}))
    with pytest.raises(SourceError):
        ADAPTERS["bybit"].fetch({"symbol": "BTCUSDT", "metric": "funding"}, None)


@respx.mock
def test_defillama_sums_usdt_usdc():
    respx.get("https://stablecoins.llama.fi/stablecoins").mock(return_value=httpx.Response(200, json={
        "peggedAssets": [
            {"id": "1", "symbol": "USDT", "circulating": {"peggedUSD": 183e9}},
            {"id": "2", "symbol": "USDC", "circulating": {"peggedUSD": 74e9}},
            {"id": "99", "symbol": "USDT", "circulating": {"peggedUSD": 1e6}}]}))

    def chart(request):
        sid = request.url.params["stablecoin"]
        v = 183e9 if sid == "1" else 74e9
        return httpx.Response(200, json=[
            {"date": "1758499200", "totalCirculatingUSD": {"peggedUSD": v}},
            {"date": "1758585600", "totalCirculatingUSD": {"peggedUSD": v + 1e9}}])

    respx.get("https://stablecoins.llama.fi/stablecoincharts/all").mock(side_effect=chart)
    obs = ADAPTERS["defillama"].fetch({"symbols": ["USDT", "USDC"]}, None)
    assert obs[0].value == pytest.approx(257.0) and obs[1].value == pytest.approx(259.0)


@respx.mock
def test_cftc_net_leveraged():
    route = respx.get("https://publicreporting.cftc.gov/resource/gpe5-46if.json").mock(return_value=httpx.Response(
        200, json=[{"report_date_as_yyyy_mm_dd": "2026-09-15T00:00:00.000",
                    "lev_money_positions_long": "40000", "lev_money_positions_short": "95000"}]))
    obs = ADAPTERS["cftc"].fetch({"dataset": "gpe5-46if", "contract_code": "097741"}, None)
    assert obs[0].date == "2026-09-15" and obs[0].value == -55000
    assert "097741" in route.calls[0].request.url.params["$where"]


def test_sosovalue_parse_variants():
    a = soso_parse({"code": 0, "data": [{"date": "2026-09-19", "totalNetInflow": 250_000_000}]})
    assert a[0].value == 250.0
    b = soso_parse({"code": 0, "data": {"list": [{"date": 1758240000000, "netInflow": "-1.2e8"}]}})
    assert b[0].value == -120.0
    with pytest.raises(SourceError):
        soso_parse({"code": 40001, "msg": "invalid api key"})


@respx.mock
def test_sosovalue_sends_key():
    route = respx.post("https://api.sosovalue.xyz/openapi/v2/etf/historicalInflowChart").mock(
        return_value=httpx.Response(200, json={"code": 0, "data": [{"date": "2026-09-19", "totalNetInflow": 1e8}]}))
    ADAPTERS["sosovalue"].fetch({"type": "us-btc-spot"}, None)
    req = route.calls[0].request
    assert req.headers["x-soso-api-key"] == "soso-key" and json.loads(req.content) == {"type": "us-btc-spot"}


@respx.mock
def test_bis_csv():
    respx.get("https://stats.bis.org/api/v1/data/WS_CBPOL/M.XM/all").mock(return_value=httpx.Response(
        200, text="FREQ,REF_AREA,TIME_PERIOD,OBS_VALUE\nM,XM,2026-07,2.0\nM,XM,2026-08,2.0\nM,XM,2026-09,NaN\n"))
    obs = ADAPTERS["bis"].fetch({"flow": "WS_CBPOL", "key": "M.XM"}, None)
    assert [(o.date, o.value) for o in obs] == [("2026-07-01", 2.0), ("2026-08-01", 2.0)]


@respx.mock
def test_frankfurter():
    respx.get(url__regex=r"https://api\.frankfurter\.app/\d{4}-\d{2}-\d{2}\.\.").mock(return_value=httpx.Response(
        200, json={"base": "USD", "rates": {"2026-09-18": {"EUR": 0.85, "TRY": 41.2}, "2026-09-19": {"EUR": 0.851}}}))
    obs = ADAPTERS["frankfurter"].fetch({"currency": "TRY"}, None)
    assert [(o.date, o.value) for o in obs] == [("2026-09-18", 41.2)]


@respx.mock
def test_imf_datamapper():
    respx.get("https://www.imf.org/external/datamapper/api/v1/GGXWDG_NGDP/USA").mock(return_value=httpx.Response(
        200, json={"values": {"GGXWDG_NGDP": {"USA": {"2024": 121.0, "2025": 122.5}}}}))
    obs = ADAPTERS["imf"].fetch({"indicator": "GGXWDG_NGDP", "code": "USA"}, None)
    assert obs[-1] == type(obs[0])("2025-01-01", 122.5)
    respx.get("https://www.imf.org/external/datamapper/api/v1/GGXWDG_NGDP/XXX").mock(
        return_value=httpx.Response(200, json={"values": {}}))
    with pytest.raises(SourceError):
        ADAPTERS["imf"].fetch({"indicator": "GGXWDG_NGDP", "code": "XXX"}, None)


@respx.mock
def test_worldbank():
    respx.get("https://api.worldbank.org/v2/country/US/indicator/NE.RSB.GNFS.ZS").mock(return_value=httpx.Response(
        200, json=[{"page": 1}, [{"date": "2024", "value": -2.9}, {"date": "2025", "value": None}]]))
    obs = ADAPTERS["worldbank"].fetch({"indicator": "NE.RSB.GNFS.ZS", "code": "US"}, None)
    assert obs == [type(obs[0])("2024-01-01", -2.9)]
    respx.get("https://api.worldbank.org/v2/country/XX/indicator/NE.RSB.GNFS.ZS").mock(return_value=httpx.Response(
        200, json=[{"message": [{"id": "120", "value": "Invalid value"}]}]))
    with pytest.raises(SourceError):
        ADAPTERS["worldbank"].fetch({"indicator": "NE.RSB.GNFS.ZS", "code": "XX"}, None)


DSD_XML = """<?xml version="1.0"?>
<message:Structure xmlns:message="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/message"
  xmlns:structure="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/structure">
 <message:Structures><structure:DataStructures><structure:DataStructure id="DSD_KEI">
  <structure:DataStructureComponents><structure:DimensionList>
   <structure:Dimension id="REF_AREA" position="1"/>
   <structure:Dimension id="FREQ" position="2"/>
   <structure:Dimension id="MEASURE" position="3"/>
   <structure:Dimension id="TRANSFORMATION" position="4"/>
   <structure:TimeDimension id="TIME_PERIOD" position="5"/>
  </structure:DimensionList></structure:DataStructureComponents>
 </structure:DataStructure></structure:DataStructures></message:Structures></message:Structure>"""

OECD_CSV = """DATAFLOW,REF_AREA,FREQ,MEASURE,TRANSFORMATION,TIME_PERIOD,OBS_VALUE
OECD.SDD.STES:DSD_KEI@DF_KEI(4.0),USA,M,PRVM,_Z,2026-06,102.1
OECD.SDD.STES:DSD_KEI@DF_KEI(4.0),USA,M,PRVM,GY,2026-06,1.4
OECD.SDD.STES:DSD_KEI@DF_KEI(4.0),USA,M,PRVM,GY,2026-07,1.9
OECD.SDD.STES:DSD_KEI@DF_KEI(4.0),USA,M,IRLT,_Z,2026-07,4.25
"""


def test_oecd_structure_and_selection():
    assert parse_dimensions(DSD_XML) == ["REF_AREA", "FREQ", "MEASURE", "TRANSFORMATION"]
    obs = select_series(OECD_CSV, [{"MEASURE": "PRVM", "TRANSFORMATION": "GY"}])
    assert [(o.date, o.value) for o in obs] == [("2026-06-01", 1.4), ("2026-07-01", 1.9)]
    with pytest.raises(SourceError) as e:
        select_series(OECD_CSV, [{"MEASURE": "NOPE"}])
    assert "IRLT" in str(e.value)  # error lists what is available


@respx.mock
def test_oecd_adapter_builds_key_from_structure():
    respx.get(url__regex=r".*/dataflow/OECD\.SDD\.STES/DSD_KEI@DF_KEI/latest.*").mock(
        return_value=httpx.Response(200, text=DSD_XML))
    data = respx.get(url__regex=r".*/data/OECD\.SDD\.STES,DSD_KEI@DF_KEI/USA\.M\.\..*").mock(
        return_value=httpx.Response(200, text=OECD_CSV))
    obs = ADAPTERS["oecd"].fetch({"agency": "OECD.SDD.STES", "flow": "DSD_KEI@DF_KEI",
                                  "dims": {"REF_AREA": "USA", "FREQ": "M"},
                                  "prefer": [{"MEASURE": "IRLT"}]}, None)
    assert obs[-1].value == 4.25 and data.called


def test_forexfactory_parse():
    ev = ff_parse([{"title": "Federal Funds Rate", "country": "USD", "date": "2026-10-28T14:00:00-04:00",
                    "impact": "High", "forecast": "3.75%", "previous": "4.00%"},
                   {"title": "broken", "country": "EUR", "date": "not a date"}])
    assert len(ev) == 1
    assert ev[0]["ts"] == "2026-10-28T18:00:00+00:00" and ev[0]["currency"] == "USD"
