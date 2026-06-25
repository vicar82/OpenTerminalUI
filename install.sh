#!/usr/bin/env bash
# ============================================================================
# OpenTerminalUI — локальный установщик (macOS / Linux / WSL).
#
#   ./install.sh
#
# Создаёт .env, генерирует секреты и пароль администратора, устанавливает
# Python-зависимости, собирает frontend и запускает сервер на
# http://localhost:8000.
# ============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

ENV_FILE="$ROOT_DIR/.env"
PORT="${APP_PORT:-8000}"

cyan() { printf "\033[36m%s\033[0m\n" "$1"; }
green() { printf "\033[32m%s\033[0m\n" "$1"; }
yellow() { printf "\033[33m%s\033[0m\n" "$1"; }

detect_os() {
  local uname_s
  uname_s="$(uname -s 2>/dev/null || echo unknown)"
  case "$uname_s" in
    Darwin) OTUI_OS="macos" ;;
    Linux)
      if grep -qiE "microsoft|wsl" /proc/version 2>/dev/null; then
        OTUI_OS="wsl"
      else
        OTUI_OS="linux"
      fi
      ;;
    MINGW*|MSYS*|CYGWIN*) OTUI_OS="windows" ;;
    *) OTUI_OS="unknown" ;;
  esac

  if command -v python3.11 >/dev/null 2>&1; then
    PY_BIN="python3.11"
  elif command -v python3 >/dev/null 2>&1; then
    PY_BIN="python3"
  elif command -v python >/dev/null 2>&1; then
    PY_BIN="python"
  else
    PY_BIN=""
  fi
}

open_browser() {
  local url="$1"
  case "$OTUI_OS" in
    macos) command -v open >/dev/null 2>&1 && open "$url" >/dev/null 2>&1 || true ;;
    linux) command -v xdg-open >/dev/null 2>&1 && xdg-open "$url" >/dev/null 2>&1 || true ;;
    wsl|windows)
      if command -v powershell.exe >/dev/null 2>&1; then
        powershell.exe -NoProfile Start-Process "$url" >/dev/null 2>&1 || true
      elif command -v cmd.exe >/dev/null 2>&1; then
        cmd.exe /c start "" "$url" >/dev/null 2>&1 || true
      fi
      ;;
  esac
}

gen_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
  elif [ -n "${PY_BIN:-}" ]; then
    "$PY_BIN" -c "import secrets; print(secrets.token_hex(32))"
  else
    head -c32 /dev/urandom | od -An -tx1 | tr -d ' \n'
  fi
}

env_get() {
  local key="$1"
  [ -f "$ENV_FILE" ] || { echo ""; return; }
  sed -n "s/^${key}=//p" "$ENV_FILE" | head -n1
}

env_set() {
  local key="$1" value="$2" tmp
  tmp="$(mktemp)"
  if [ -f "$ENV_FILE" ] && grep -q "^${key}=" "$ENV_FILE"; then
    awk -v k="$key" -v v="$value" 'BEGIN{FS=OFS="="} $1==k{print k"="v; next} {print}' "$ENV_FILE" > "$tmp"
    mv "$tmp" "$ENV_FILE"
  else
    rm -f "$tmp"
    printf "%s=%s\n" "$key" "$value" >> "$ENV_FILE"
  fi
}

ensure_var() {
  local key="$1" value="$2"
  local current
  current="$(env_get "$key")"
  if [ -z "$current" ]; then
    env_set "$key" "$value"
  fi
}

cyan "==> Установщик OpenTerminalUI"

# --- 0. Определение ОС ------------------------------------------------------
detect_os
green "    обнаружена ОС: ${OTUI_OS}  (python: ${PY_BIN:-не найден})"
if [ "$OTUI_OS" = "windows" ]; then
  yellow "    Обнаружена Windows. Для удобства используйте PowerShell-установщик: ./install.ps1"
fi

# --- 1. Проверка зависимостей ----------------------------------------------
if [ -z "${PY_BIN:-}" ]; then
  yellow "    Python не найден; установите Python 3.11+"
  exit 1
fi
command -v npm >/dev/null 2>&1 || { yellow "    npm не найден; установите Node 20+"; exit 1; }

# --- 2. Создание .env -------------------------------------------------------
if [ ! -f "$ENV_FILE" ]; then
  cp "$ROOT_DIR/.env.example" "$ENV_FILE"
  green "    создан .env из .env.example"
else
  yellow "    .env уже существует — сохраняем значения, заполняем пустые поля"
fi

# --- 3. Генерация секретов и администратора ---------------------------------
ensure_var JWT_SECRET_KEY "$(gen_secret)"
ensure_var CACHE_SIGNING_KEY "$(gen_secret)"
ensure_var BOOTSTRAP_ADMIN_EMAIL "admin@openterminal.local"

ADMIN_PASS="$(env_get BOOTSTRAP_ADMIN_PASSWORD)"
if [ -z "$ADMIN_PASS" ]; then
  ADMIN_PASS="$(gen_secret | cut -c1-20)"
  env_set BOOTSTRAP_ADMIN_PASSWORD "$ADMIN_PASS"
fi
ADMIN_EMAIL="$(env_get BOOTSTRAP_ADMIN_EMAIL)"
green "    секреты и учётная запись администратора настроены"

# --- 4. Установка Python-зависимостей и сборка frontend ---------------------
local venv_py
green "    настройка Python-бэкенда..."
[ -d "$ROOT_DIR/.venv" ] || "$PY_BIN" -m venv "$ROOT_DIR/.venv"
if [ -x "$ROOT_DIR/.venv/bin/python" ]; then
  venv_py="$ROOT_DIR/.venv/bin/python"
else
  venv_py="$ROOT_DIR/.venv/Scripts/python.exe"
fi
"$venv_py" -m pip install --quiet --upgrade pip
"$venv_py" -m pip install --quiet -r "$ROOT_DIR/backend/requirements.txt"

green "    сборка frontend..."
(cd "$ROOT_DIR/frontend" && npm ci && npm run build)

# --- 5. Миграции и создание администратора ----------------------------------
green "    выполнение миграций базы данных..."
PYTHONPATH="$ROOT_DIR" "$venv_py" -m alembic -c "$ROOT_DIR/backend/alembic.ini" upgrade head || true

green "    создание учётной записи администратора..."
PYTHONPATH="$ROOT_DIR" "$venv_py" "$ROOT_DIR/scripts/seed_admin.py"

# --- 6. Запуск сервера ------------------------------------------------------
print_credentials() {
  echo
  green "============================================================"
  green " OpenTerminalUI готов -> http://localhost:${PORT}"
  green "------------------------------------------------------------"
  green "  Войдите, используя:"
  green "    email:    ${ADMIN_EMAIL}"
  green "    password: ${ADMIN_PASS}"
  green "  (также сохранено в .env — смените пароль после первого входа)"
  green "============================================================"
  echo
  cyan "  Добавить API-ключи: ./scripts/setup-keys.sh"
}

print_credentials
open_browser "http://localhost:${PORT}"
green "    запуск сервера на http://localhost:${PORT} (Ctrl+C для остановки)..."
exec env PYTHONPATH="$ROOT_DIR" "$venv_py" -m uvicorn backend.main:app --host 0.0.0.0 --port "$PORT"
