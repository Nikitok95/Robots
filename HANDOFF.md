# Macro Carry Monitor («Макро Борд»): передача проекта

Этот файл для следующего исполнителя, человека или Claude в другом диалоге.
Прочитайте его целиком перед любыми действиями.

## 1. Идея проекта

Ежедневный макро-дашборд для трейдинга (TradeGreat / Honey Badger AI). Он
отслеживает одну связку рисков:

**ставки ФРС и BOJ → carry trade по иене → потоки в крипту (BTC) → общий риск-аппетит.**

Логика: когда спред доходностей США и Японии сужается, а иена резко
укрепляется, carry trade (занять в иенах, вложить в более доходные активы)
сворачивается. Это вызывает распродажу рисковых активов, в том числе BTC.
Дашборд собирает ранние признаки такого сценария в одном месте и шлёт алерты.

Разделы:
1. **Дашборд**, 5 групп метрик: у каждой значение, изменение за 1D/1W/1M,
   спарклайн, график по клику за 1M/3M/1Y/5Y, источник и дата.
   - Ставки и ожидания: US 2Y/10Y/10Y real, 2s10s, 5Y5Y breakeven, EFFR,
     вероятности решений ФРС на 2 заседания (расчёт из фьючерсов ZQ),
     ставка BOJ и прокси ожиданий по BOJ.
   - Спреды США − Япония: JGB 2Y/10Y, спреды US−JGB, график с USD/JPY.
   - Валюты: USD/JPY, DXY, 30D реализованная волатильность USD/JPY,
     CFTC COT по JPY (leveraged funds).
   - Крипто: BTC, нетто-потоки spot BTC ETF (день и 5 дней), Coinbase
     Premium, funding и Open Interest перпетуалов, USDT+USDC.
   - Риск-аппетит: VIX, Nasdaq 100, Brent, MOVE.
2. **Алерты**: 4 правила, пороги редактируются в UI и хранятся в БД.
   Срабатывания попадают в ленту и подсвечивают карточки.
3. **Карта мира** (ECharts): G10 + EM, еврозона окрашена единым блоком EUR.
   Раскраска по ставке ЦБ, CPI, изменению валюты за 1M или реальной ставке.
   Тултип и боковая панель страны с вкладками Макро / Бюджет / Микро / Календарь.
4. **Источники**: живой статус каждой загрузки (OK / ошибка / устарело).

Принципы: ручного ввода нет. Где бесплатного API нет, используется расчётный
прокси с пометкой в UI. У каждого значения подписаны источник и дата. Если
источник недоступен, показывается последнее значение с бейджем «устарело».
Время везде в Europe/Madrid.

## 2. Что внутри

```
backend/   FastAPI + APScheduler + SQLite (Python 3.12)
  app/adapters/     по одному классу на источник, общий интерфейс
                    (FRED, Yahoo, Минфин Японии, BOJ, CoinGecko, Coinbase, Binance,
                    Bybit, DefiLlama, CFTC, SoSoValue, BIS, ECB/Frankfurter, IMF,
                    World Bank, OECD, Forex Factory, Trading Economics, FMP)
  app/catalog.py    метрики дашборда и цепочки источников (основной → запасной)
  app/map_catalog.py индикаторы карты
  app/ingest.py     загрузка → SQLite → производные ряды
  app/alerts.py     правила алертов
  app/verify.py     живая проверка всех источников (python -m app.verify)
  config/countries.yaml   список стран (легко расширять)
  config/cb_meetings.yaml даты заседаний ЦБ (официальные, со ссылками)
  tests/            35 тестов на фикстурах, без сети
frontend/  React + TypeScript + Vite + Tailwind + ECharts, nginx в проде
docker-compose.yml   backend + frontend, том для SQLite
deploy/deploy.sh     деплой в один шаг на Linux-сервер
deploy/CLAUDE_ON_SERVER.md  как запустить Claude Code на сервере
.env.example         список ключей
README.md            полная документация и таблица источников
```

## 3. Состояние: что проверено и что нет

- Тесты бэкенда: 35 из 35 проходят. Фронтенд собирается без ошибок.
  UI проверен по скриншотам на синтетических данных.
- **Ни один внешний источник не проверен реальным запросом.** Среда
  разработки блокировала исходящую сеть. ID серий и форматы ответов взяты
  из документации. Первый прогон `python -m app.verify` на сервере и есть
  проверка.
- Ожидаемые места расхождений:
  - `SOSOVALUE_ETF_URL`: путь API SoSoValue неоднозначен, вынесен в `.env`;
  - коды мер OECD (`MEASURE`/`TRANSFORMATION`): при ошибке адаптер перечисляет доступные значения;
  - код еврозоны в IMF (`EURO` в `countries.yaml`);
  - Binance и Bybit блокируют IP США: с серверов в ЕС должно работать.
- Docker-образы не собирались: в среде разработки не было Docker.
- **В дашборде нет авторизации.** Доступ закрывается на уровне reverse proxy.

## 4. Ключи (.env, только на сервере, никогда не в чат и не в git)

| Переменная | Нужна | Где взять |
|---|---|---|
| `FRED_API_KEY` | да | бесплатно: https://fred.stlouisfed.org/docs/api/api_key.html |
| `SOSOVALUE_API_KEY` | да | бесплатно: https://sosovalue.com/developer |
| `COINGECKO_API_KEY` | нет | бесплатный Demo key |
| `TRADINGECONOMICS_API_KEY`, `FMP_API_KEY` | нет, платно | PMI, зарплаты, расширенный календарь |

## 5. Как развернуть

```bash
unzip macro-dashboard-src.zip && cd macro-dashboard
git init -b macro-dashboard && git add -A && git commit -m "Macro Dashboard: initial import"
git remote add origin <URL репозитория> && git push -u origin macro-dashboard

# на сервере
REPO=<URL репозитория> BRANCH=macro-dashboard bash deploy/deploy.sh   # 1-й запуск создаст .env
nano /opt/macro-dashboard/.env                                        # ключи
REPO=<URL репозитория> BRANCH=macro-dashboard bash deploy/deploy.sh   # сборка, старт, verify
```

Приложение слушает `http://localhost:$WEB_PORT` (8080 по умолчанию). Фронтенд
и `/api` работают с одного адреса: nginx в контейнере `frontend`
проксирует `/api` на бэкенд. Для публикации достаточно направить домен
(например, `macro.tradegreat.io`) на этот порт через Caddy или nginx на шлюзе
и закрыть его авторизацией (SSO CRM / forward_auth / basic auth).

## 6. Промпт для Claude в другом диалоге

Скопируйте текст ниже в новый диалог вместе с архивом `macro-dashboard-src.zip`:

---

> Прикладываю архив `macro-dashboard-src.zip`: это проект Macro Carry Monitor
> («Макро Борд»), готовый макро-дашборд (FastAPI + SQLite + React/ECharts,
> Docker Compose). Сначала распакуй его и полностью прочитай
> `macro-dashboard/HANDOFF.md`, потом `README.md`, `.env.example` и `deploy/`.
> Код не переписывай и не «улучшай» без моего согласия: задача — залить и
> развернуть.
>
> 1. Распакуй: `unzip macro-dashboard-src.zip` (корень — папка `macro-dashboard/`,
>    внутри `docker-compose.yml`, `backend/`, `frontend/`, `deploy/`).
> 2. Проверь целостность: `cd backend && python -m venv .venv &&
>    .venv/bin/pip install -r requirements-dev.txt && .venv/bin/pytest` —
>    должно быть 35 passed. `cd frontend && npm ci && npm run build` — без ошибок.
> 3. Залей в GitHub отдельной веткой `macro-dashboard` в репозиторий, к
>    которому у тебя есть доступ на запись (`git init -b macro-dashboard`,
>    commit, push). Не смешивай с другими проектами в одной ветке.
> 4. Разверни на crm-server через `deploy/deploy.sh` с `REPO=` и
>    `BRANCH=macro-dashboard`. Ключи FRED и SoSoValue я положу в `.env` на сервере
>    сам; не выводи содержимое `.env` в чат и не коммить его. На сервере уже
>    работает CRM: не трогай чужие контейнеры, сети и файлы вне
>    `/opt/macro-dashboard`. Если порт 8080 занят, поменяй `WEB_PORT` в `.env`.
> 5. Опубликуй на `macro.tradegreat.io` через Caddy на шлюзе, **только за
>    единой сессией CRM** (в самом дашборде авторизации нет). Добавь плитку
>    «Макро Борд» в реестр, как сделано для Tester.
> 6. Выполни `docker compose exec -T backend python -m app.verify` и
>    `... python -m app.verify --macro` и пришли сводку: какие источники OK,
>    какие FAIL и почему. Это первая проверка на реальной сети. Исправления
>    адаптеров предлагай отдельно, до правок покажи мне diff.
> 7. В конце пришли: ссылку на ветку, URL дашборда, вывод verify, список
>    того, что не заработало.

---

## 7. Что дальше

1. Прогнать `verify` и починить адаптеры, которые не заработали.
2. Сверить значения с первоисточниками (FRED, Минфин Японии, CME FedWatch
   для вероятностей ФРС).
3. При необходимости: уведомления об алертах в Telegram, обновление дат
   заседаний ЦБ на 2027 год в `config/cb_meetings.yaml`.
