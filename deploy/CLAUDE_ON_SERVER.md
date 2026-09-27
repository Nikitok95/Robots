# Claude Code на сервере: деплой Macro Carry Monitor

Облачная сессия Claude не может подключиться к серверу по SSH: исходящий SSH
там закрыт. Поэтому Claude Code запускается на самом сервере, а вы управляете
им из claude.ai/code или мобильного приложения Claude (Remote Control).

Нужен тариф Pro, Max, Team или Enterprise. Remote Control работает только при
входе через аккаунт claude.ai: с `ANTHROPIC_API_KEY` или `claude setup-token`
он не работает.

## 1. Зайти на сервер и подготовить его (один раз)

```bash
ssh user@CRM_server

# Docker (если его нет) и право запускать его без sudo
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER && newgrp docker

# tmux, чтобы Claude продолжал работать после отключения SSH
sudo apt-get update && sudo apt-get install -y tmux git
```

## 2. Код проекта на сервере

Вариант A. Если у Claude есть доступ к GitHub и ветка запушена:
```bash
sudo mkdir -p /opt/macro-dashboard && sudo chown $USER /opt/macro-dashboard
git clone -b claude/macro-dashboard-rates-crypto-4rir90 https://github.com/Nikitok95/Robots.git /opt/macro-dashboard
```

Вариант B. Без GitHub, из файла `macro-dashboard.bundle`, который прислал Claude.
С вашего компьютера:
```bash
scp macro-dashboard.bundle user@CRM_server:/tmp/
```
На сервере:
```bash
sudo mkdir -p /opt/macro-dashboard && sudo chown $USER /opt/macro-dashboard
git clone -b claude/macro-dashboard-rates-crypto-4rir90 /tmp/macro-dashboard.bundle /opt/macro-dashboard
```

## 3. Ключи — вписываете сами, в чат не отправляете

```bash
cd /opt/macro-dashboard
cp .env.example .env && chmod 600 .env
nano .env        # FRED_API_KEY=..., SOSOVALUE_API_KEY=...; при занятом 8080 поменяйте WEB_PORT
```

## 4. Установить Claude Code и войти

```bash
curl -fsSL https://claude.ai/install.sh | bash
claude           # при первом запуске выберите вход через аккаунт claude.ai
```
Браузер на сервере не откроется. Скопируйте показанную ссылку, откройте её
на своём компьютере или телефоне, войдите и вставьте код в терминал
(«Paste code here»). После входа выйдите командой `/exit`.

## 5. Запустить Remote Control в tmux

```bash
cd /opt/macro-dashboard
tmux new -s claude
claude remote-control --name "CRM_server deploy"
```
Отключиться от tmux, не останавливая Claude: `Ctrl+B`, затем `D`.
Потом можно выйти из SSH. Вернуться к сессии: `tmux attach -t claude`.

Сессия появится в claude.ai/code и в приложении Claude на вкладке **Code**
под именем «CRM_server deploy». Каждую команду Claude будет присылать вам
на подтверждение. Не давайте ему широких разрешений вроде `sudo *`: Docker
уже работает без sudo (шаг 1).

## 6. Что написать Claude в этой сессии

> Ты на сервере CRM_server в /opt/macro-dashboard (проект Macro Carry Monitor).
> На сервере уже работает CRM — ничего не трогай вне этой папки и чужие
> контейнеры. .env с ключами уже заполнен, не выводи его содержимое.
> 1) Проверь, что порт из WEB_PORT в .env свободен (ss -ltn); если занят — скажи мне.
> 2) Запусти `bash deploy/deploy.sh`.
> 3) Пришли вывод `python -m app.verify` и `python -m app.verify --macro`
>    (docker compose exec -T backend ...), сгруппируй ошибки по источникам и
>    предложи исправления в адаптерах. Код не меняй без моего подтверждения.
> 4) Проверь, что UI открывается: curl http://localhost:$WEB_PORT/api/health.

## Если нужен доступ из интернета

UI слушает порт `WEB_PORT` (8080 по умолчанию). Откройте его в файрволе
(`sudo ufw allow 8080/tcp`) или поставьте проект за уже работающий на сервере
reverse proxy (nginx или Caddy) на отдельном поддомене с HTTPS. Авторизации
в дашборде нет, поэтому публично его лучше закрыть basic auth на прокси.
