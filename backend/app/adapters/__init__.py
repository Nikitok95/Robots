from .base import CalendarAdapter, MissingKeyError, Obs, SourceAdapter, SourceError, http
from .binance import BinanceAdapter
from .bis import BisAdapter
from .boj import BojAdapter
from .bybit import BybitAdapter
from .cftc import CftcAdapter
from .coinbase import CoinbaseAdapter
from .coingecko import CoinGeckoAdapter
from .defillama import DefiLlamaAdapter
from .fmp import FmpCalendar
from .forexfactory import ForexFactoryCalendar
from .frankfurter import FrankfurterAdapter
from .fred import FredAdapter
from .imf import ImfAdapter
from .mof_jgb import MofJgbAdapter
from .oecd import OecdAdapter
from .sosovalue import SoSoValueAdapter
from .tradingeconomics import TradingEconomicsAdapter, TradingEconomicsCalendar
from .worldbank import WorldBankAdapter
from .yahoo import YahooAdapter

ADAPTERS: dict[str, SourceAdapter] = {a.name: a for a in [
    FredAdapter(), YahooAdapter(), MofJgbAdapter(), BojAdapter(), CoinGeckoAdapter(), CoinbaseAdapter(),
    BinanceAdapter(), BybitAdapter(), DefiLlamaAdapter(), CftcAdapter(), SoSoValueAdapter(), BisAdapter(),
    FrankfurterAdapter(), ImfAdapter(), WorldBankAdapter(), OecdAdapter(), TradingEconomicsAdapter(),
]}

# Order = priority. The free feed is always on; paid ones join when a key is set.
CALENDARS: list[CalendarAdapter] = [ForexFactoryCalendar(), TradingEconomicsCalendar(), FmpCalendar()]

__all__ = ["ADAPTERS", "CALENDARS", "Obs", "SourceAdapter", "CalendarAdapter", "SourceError",
           "MissingKeyError", "http"]
