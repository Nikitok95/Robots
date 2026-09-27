# Macro Carry Monitor

> Передача проекта, идея, статус и промпт для развёртывания: [`HANDOFF.md`](HANDOFF.md).

Дашборд для ежедневного мониторинга связки: ставки ФРС и BOJ, carry trade по иене,
потоки в крипту (BTC) и общий риск-аппетит. Отдельная вкладка: карта мира
с G10 и EM-валютами.

- **Backend:** Python FastAPI, APScheduler, SQLite (кеш и история).
- **Frontend:** React + TypeScript + Vite, Tailwind, ECharts.
- **Запуск:** Docker Compose. API-ключи хранятся только в `.env` бэкенда,
  браузер ходит только в свой `/api`.
- Все даты и время показываются в часовом поясе **Europe/Madrid**.
- Ручного ввода нет. Метрики без бесплатного API заменены расчётными прокси
  с явной пометкой в UI.

## Запуск (self-hosted, например Hetzner)

Проще всего запустить скрипт: он ставит Docker, клонирует ветку, создаёт `.env`,
собирает, запускает и проверяет источники:

```bash
curl -fsSLO https://raw.githubusercontent.com/Nikitok95/Robots/claude/macro-dashboard-rates-crypto-4rir90/deploy/deploy.sh
bash deploy.sh      # 1-й запуск создаст /opt/macro-dashboard/.env — впишите ключи
bash deploy.sh      # 2-й запуск: сборка, старт, проверка источников
```

Деплой силами Claude Code, запущенного на сервере: см. `deploy/CLAUDE_ON_SERVER.md`.

Вручную:

```bash
git clone <repo> && cd <repo>
cp .env.example .env      # впишите ключи, см. ниже
docker compose up -d --build
```

UI откроется на `http://<сервер>:8080` (порт задаётся через `WEB_PORT`).
При первом старте бэкенд запускает полную загрузку истории (до 6 лет),
это занимает несколько минут. Прогресс видно на вкладке **Источники**.

### Проверка источников после деплоя

Endpoint'ы нельзя было проверить из среды разработки: там закрыт исходящий
доступ. Поэтому сразу после деплоя выполните:

```bash
docker compose exec backend python -m app.verify           # метрики дашборда, ZQ, календари
docker compose exec backend python -m app.verify --macro   # + все индикаторы карты
```

Для каждой серии команда печатает `OK / FAIL / KEY`, число точек, дату
и значение последней точки. В БД она ничего не пишет. Тот же статус постоянно
виден в UI на вкладке **Источники**.

### API-ключи

| Переменная | Нужна? | Для чего | Где взять |
|---|---|---|---|
| `FRED_API_KEY` | **да** | US 2Y/10Y, TIPS, 2s10s, 5Y5Y, EFFR, диапазон ставки ФРС, VIX, Nasdaq 100 | бесплатно: https://fred.stlouisfed.org/docs/api/api_key.html |
| `SOSOVALUE_API_KEY` | **да** | нетто-потоки spot BTC ETF | бесплатно: https://sosovalue.com/developer |
| `COINGECKO_API_KEY` | нет | повышает лимиты CoinGecko (без ключа тоже работает) | бесплатный Demo key |
| `TRADINGECONOMICS_API_KEY` | нет, платно | PMI, рост зарплат, расширенный календарь | https://tradingeconomics.com/api |
| `FMP_API_KEY` | нет, платно | экономический календарь | https://site.financialmodelingprep.com |

Без платных ключей PMI и рост зарплат показываются как «нет бесплатного
источника». Вместо PMI выводится OECD Business Confidence с пометкой «прокси».

## Источники данных

Все значения в UI подписаны: источник, дата данных, время загрузки.
Если источник упал, остаётся последнее значение с бейджем **«устарело»**.

| Метрика | Источник | Endpoint / ID | Частота | Ключ |
|---|---|---|---|---|
| US 2Y / 10Y / 10Y real / 2s10s | FRED | `DGS2`, `DGS10`, `DFII10`, `T10Y2Y` | D | FRED |
| 5Y5Y breakeven | FRED | `T5YIFR` | D | FRED |
| EFFR, диапазон ставки ФРС | FRED | `EFFR`, `DFEDTARU`, `DFEDTARL` | D | FRED |
| Вероятности ФРС (2 заседания) | расчёт из фьючерсов 30-Day Fed Funds | Yahoo `ZQ{месяц}{год}.CBT` (неофиц.) | D | — |
| Ставка BOJ | BOJ Time-Series API | `FM01 / STRDCLUCON` (O/N call rate) | D | — |
| Ожидания по BOJ | **прокси**: JGB 1Y − ставка BOJ | расчёт | D | — |
| JGB 1Y / 2Y / 10Y | Минфин Японии | `jgbcme.csv`, `historical/jgbcme_all.csv` | D | — |
| Спреды US−JGB 2Y/10Y | расчёт | — | D | — |
| USD/JPY | Yahoo `JPY=X` → запасной FRED `DEXJPUS` | | D | — |
| DXY | Yahoo `DX-Y.NYB` (неофиц.) | | D | — |
| USD/JPY vol | **замена**: 30D реализованная волатильность (бесплатной 1M implied нет) | расчёт | D | — |
| CFTC COT JPY, leveraged funds | CFTC Socrata, TFF futures-only | `gpe5-46if`, код рынка `097741` | W | — |
| BTC | CoinGecko → запасной Coinbase | `/coins/bitcoin/market_chart` | D (крипто — раз в час) | опц. |
| Spot BTC ETF flows, сумма 5 дней | SoSoValue | `SOSOVALUE_ETF_URL`, тип `us-btc-spot` | D | SoSoValue |
| Coinbase Premium | Coinbase `BTC-USD` vs Binance `BTCUSDT` (дневные свечи) | расчёт | D | — |
| Funding | Binance `fapi/v1/fundingRate` → запасной Bybit | среднее 8-часовых ставок за сутки | D | — |
| Open Interest | Bybit `v5/market/open-interest` → запасной Binance | в BTC | D | — |
| USDT + USDC | DefiLlama stablecoins (id ищутся по символу) | | D | — |
| VIX, Nasdaq 100 | FRED `VIXCLS`, `NASDAQ100` → запасной Yahoo | | D | FRED |
| Brent | Yahoo `BZ=F` → запасной FRED `DCOILBRENTEU` | | D | — |
| MOVE | Yahoo `^MOVE` (неофиц.) | | D | — |

Карта мира:

| Показатель | Источник |
|---|---|
| Курс к USD | ECB через Frankfurter (все 22 валюты списка) |
| Ставка ЦБ и история решений | BIS `WS_CBPOL` (у Сингапура ставки нет: MAS таргетирует курс) |
| CPI г/г | BIS `WS_LONG_CPI`, запасной вариант OECD Prices |
| Core CPI | OECD `DF_PRICES_ALL` |
| Доходность 10Y | OECD `DF_KEI / IRLT`; для США FRED, для Японии Минфин |
| ВВП к/к и г/г | OECD `DF_QNA_EXPENDITURE_GROWTH_OECD` |
| Годовой рост ВВП, безработица, счёт текущих операций | IMF DataMapper (`NGDP_RPCH`, `LUR`, `BCA_NGDPD`) |
| Бюджет: баланс, госдолг, доходы, расходы (% ВВП, 5 лет + прогноз) | IMF DataMapper (`GGXCNL_NGDP`, `GGXWDG_NGDP`, `GGR_NGDP`, `GGX_NGDP`) |
| Торговый баланс | World Bank `NE.RSB.GNFS.ZS` |
| Промпроизводство, розница, деловое и потребительское доверие | OECD `DF_KEI` |
| Цены на жильё | BIS `WS_SPP` |
| PMI, рост зарплат | Trading Economics (платно, опционально) |
| Календарь на 2 недели | Forex Factory JSON (бесплатно: USD EUR GBP JPY CHF CAD AUD NZD CNY). С ключом добавляются TE и FMP |
| Даты заседаний ЦБ | `backend/config/cb_meetings.yaml` (официальные графики со ссылками), затем календарь |

**Не проверено реальным запросом:** все endpoint'ы кроме GeoJSON карты. Среда
разработки блокировала исходящие запросы, поэтому ID серий и форматы ответов
взяты из документации и поиска. Каждый адаптер покрыт тестами на фикстурах
документированного формата. Реальную работу подтверждает
`python -m app.verify` на сервере. Места, где расхождение наиболее вероятно:
- путь SoSoValue: настраивается через `SOSOVALUE_ETF_URL`;
- коды мер OECD: при ошибке адаптер перечисляет доступные значения;
- код еврозоны в IMF (`EURO` в `countries.yaml`).

## Алерты

Правила и пороги редактируются во вкладке **Алерты** и хранятся в SQLite.
После каждой загрузки и при изменении порогов правила пересчитываются за
последние 60 дней. Срабатывания пишутся в ленту и подсвечивают карточки
на главной.

1. USD/JPY падает (иена укрепляется) больше чем на X% за день **и** отток из ETF в этот день.
2. US 10Y real растёт больше чем на X б.п. за неделю **и** MOVE растёт за неделю.
3. Притоки в ETF N дней подряд **и** USD/JPY в диапазоне **и** funding ниже порога.
4. Funding выше порога **и** рост OI больше X% за 3 дня.

## Расписание

Настраивается в `.env`, cron в часовом поясе Europe/Madrid:
- `markets` (ставки, FX, риск, ZQ) — 07:30 и 23:30;
- `crypto` — каждый час;
- `macro` (карта, календарь) — 06:00. Месячные и годовые ряды не
  перезапрашиваются чаще раза в 20 часов.

Кнопка **«Обновить сейчас»** запускает `markets` и `crypto` принудительно.
Загрузка инкрементальная: запрашиваются только даты после последней
сохранённой (с небольшим перекрытием на ревизии).

## Как добавить страну

Допишите запись в `backend/config/countries.yaml`: коды ISO/BIS/OECD/IMF/World Bank
и имя полигона из `frontend/public/world.json` (`properties.name`). Мелкие
территории задаются через `point: [lon, lat]`. Члены еврозоны добавляются
в секцию `eurozone`.

## Разработка

```bash
# backend
cd backend && python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest                      # тесты адаптеров, расчётов, API
.venv/bin/uvicorn app.main:app --reload
# frontend
cd frontend && npm install && npm run dev   # проксирует /api на :8000
```

Структура:

```
backend/app/adapters/   один класс на источник, общий интерфейс SourceAdapter
backend/app/catalog.py  метрики дашборда и цепочки источников
backend/app/map_catalog.py  индикаторы карты
backend/app/ingest.py   загрузка → SQLite → производные ряды
backend/app/alerts.py   правила алертов
backend/app/verify.py   живая проверка источников
frontend/src/pages      Дашборд, Карта, Алерты, Источники
```
