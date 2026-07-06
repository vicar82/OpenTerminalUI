# OpenTerminalUI (русскоязычный форк)

<p align="center">
  <img src="assets/logo.png" alt="OpenTerminalUI logo" width="560" />
</p>

<p align="center">
  <strong>Открытый финансовый терминал для трейдеров, исследователей и квантовых команд.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-0.5.0-0f172a" alt="Version 0.5.0" />
  <img src="https://img.shields.io/badge/python-3.11-3776AB?logo=python&logoColor=white" alt="Python 3.11" />
  <img src="https://img.shields.io/badge/node-22-339933?logo=node.js&logoColor=white" alt="Node 22" />
  <img src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black" alt="React 18" />
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License" />
</p>

Этот репозиторий — русскоязычный форк [OpenTerminalUI](https://github.com/Hitheshkaranth/OpenTerminalUI).

В форке выполнены следующие изменения:

- **Интерфейс переведён на русский язык** — основные надписи, кнопки, меню и статусные сообщения.
- **Удалён Docker** — больше нет `Dockerfile`, `docker-compose.yml` и `.dockerignore`.
- **Добавлен нормальный установщик для Debian/Ubuntu** — ставит приложение в `/opt/openterminalui`, настраивает пользователя, данные и `systemd`-сервис.
- **Локальные установщики** (`install.sh` / `install.ps1`) больше не используют Docker и сразу запускают сервер на `http://localhost:8000`.
- **Заменён индийский рынок (NSE/BSE) на российский (MOEX)** — индексы IMOEX/RTSI, акции российских эмитентов через API Московской биржи.
- **Добавлена поддержка self-hosted Ollama** — локальная LLM по умолчанию работает через `http://localhost:11434/v1/chat/completions`, без внешних API-ключей.

---

## Быстрый старт

### Debian / Ubuntu (рекомендуется)

```bash
curl -fsSL https://raw.githubusercontent.com/vicar82/OpenTerminalUI/main/scripts/install-debian.sh | sudo bash
```

После установки сервис автоматически запускается и слушает `http://localhost:8000`. Учётные данные администратора выводятся в конце установки.

Управление сервисом:

```bash
systemctl status openterminalui
systemctl stop openterminalui
systemctl restart openterminalui
```

Просмотр логов:

```bash
journalctl -u openterminalui -f
```

Удаление:

```bash
sudo ./scripts/uninstall-debian.sh
```

### macOS / Linux / WSL (локальный запуск)

```bash
git clone https://github.com/vicar82/OpenTerminalUI.git
cd OpenTerminalUI
./install.sh
```

Установщик создаёт `.env`, генерирует секреты, устанавливает Python-зависимости, собирает frontend и запускает сервер.

### Windows (PowerShell)

```powershell
./install.ps1
```

---

## Требования

| Компонент | Минимум | Рекомендуется |
|-----------|---------|---------------|
| ОС | Linux, macOS, Windows 10+ | Ubuntu 22.04+ / Debian 12+ |
| CPU | 2 ядра | 4+ ядра |
| RAM | 4 GB | 8 GB+ |
| Диск | 2 GB | 10 GB+ (кэш исторических данных) |
| Браузер | Chrome 90+, Firefox 90+, Safari 15+, Edge 90+ | Последний Chrome или Firefox |

### Программные зависимости

| ПО | Версия | Примечание |
|----|--------|------------|
| Python | 3.11+ | Обязательно |
| Node.js | 22+ | Для сборки frontend |
| Git | 2.30+ | Для клонирования |

Для Debian/Ubuntu установщик поставит все зависимости самостоятельно.

---

## Поддерживаемые рынки

| Рынок | Источник данных | Примечания |
|-------|-----------------|------------|
| Россия (MOEX) | [MOEX ISS API](https://www.moex.com/a2193) | Акции Т+2 (`TQBR`), индексы IMOEX и RTSI, исторические свечи |
| США (NYSE/NASDAQ) | Yahoo Finance / Finnhub / FMP | Акции, ETF, фьючерсы, фундаментальные данные |

Индийский рынок (NSE/BSE) и интеграция Zerodha Kite удалены.

---

## Self-hosted Ollama

По умолчанию AI-агент и эмоциональный анализ новостей работают через локальную Ollama:

```bash
ollama run llama3
```

Переменные окружения (заполняются автоматически установщиком):

```dotenv
AI_PROVIDER=ollama
AGENT_PROVIDER=ollama
AGENT_MODEL=llama3
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3
```

Если Ollama не запущена, приложение продолжит работу с резервными данными.

---

## Переменные окружения

Ключи API необязательны — платформа работает на встроенных резервных данных. Добавьте ключи, чтобы разблокировать полный доступ к данным:

| Переменная | Назначение |
|------------|------------|
| `FMP_API_KEY` | Financial Modeling Prep — акции США, фундаментал, отчётность |
| `FINNHUB_API_KEY` | Finnhub — WebSocket-тики США в реальном времени |
| `OPENROUTER_API_KEY` | OpenRouter — встроенный агент и эмоциональный анализ новостей |
| `OPENAI_API_KEY` | OpenAI — альтернативный провайдер LLM |
| `OLLAMA_HOST` | Self-hosted Ollama — адрес API, по умолчанию `http://localhost:11434` |
| `OLLAMA_MODEL` | Модель Ollama, по умолчанию `llama3` |
| `JWT_SECRET_KEY` | Подпись JWT (генерируется установщиком) |
| `CACHE_SIGNING_KEY` | Подпись кэша (генерируется установщиком) |

Добавить или обновить ключи удобнее всего через мастер:

```bash
./scripts/setup-keys.sh
```

---

## Разработка

### Бэкенд

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
PYTHONPATH=. uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend

```bash
cd frontend && npm ci && npm run dev
```

- Бэкенд API: `http://127.0.0.1:8000`
- Frontend dev-сервер: `http://127.0.0.1:5173`

### Тестирование

```bash
# Бэкенд
PYTHONPATH=. python -m compileall backend
PYTHONPATH=. pytest backend/tests -q

# Frontend
cd frontend && npm run build && npx vitest run

# Все проверки
make gate
```

---

## Горячие клавиши

| Сочетание | Действие |
|-----------|----------|
| `Ctrl+G` | GO Bar — поиск тикера и навигация |
| `Ctrl+K` | Командная палитра — нечёткий поиск по функциям |
| `Ctrl+J` | AI-агент — открыть/закрыть панель агента |
| `F1`–`F9` | Переключение рабочих пространств |
| `1`–`7` | Горячие клавиши таймфреймов на графиках |
| `Esc` | Закрыть активную панель или диалог |

---

## Лицензия

[MIT](LICENSE) — свободно использовать, изменять и распространять.
