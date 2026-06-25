#!/usr/bin/env bash
# ============================================================================
# OpenTerminalUI — установщик для Debian/Ubuntu.
#
#   curl -fsSL https://raw.githubusercontent.com/vicar82/OpenTerminalUI/main/scripts/install-debian.sh | sudo bash
#   sudo ./scripts/install-debian.sh
#
# Устанавливает приложение в /opt/openterminalui, настраивает systemd-сервис
# и запускает веб-интерфейс на http://localhost:8000.
# ============================================================================
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Ошибка: этот установщик должен запускаться от root (используйте sudo)." >&2
  exit 1
fi

APP_NAME="openterminalui"
APP_USER="openterminalui"
APP_GROUP="openterminalui"
INSTALL_DIR="/opt/${APP_NAME}"
DATA_DIR="/var/lib/${APP_NAME}"
LOG_DIR="/var/log/${APP_NAME}"
SERVICE_NAME="${APP_NAME}.service"
REPO_URL="https://github.com/vicar82/OpenTerminalUI.git"
PORT="${APP_PORT:-8000}"

cyan() { printf "\033[36m%s\033[0m\n" "$1"; }
green() { printf "\033[32m%s\033[0m\n" "$1"; }
yellow() { printf "\033[33m%s\033[0m\n" "$1"; }
red() { printf "\033[31m%s\033[0m\n" "$1"; }

gen_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
  else
    python3.11 -c "import secrets; print(secrets.token_hex(32))"
  fi
}

cyan "==> Установщик OpenTerminalUI для Debian/Ubuntu"

# --- 1. Установка системных зависимостей -----------------------------------
yellow "    обновление пакетов и установка зависимостей..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq \
  git curl ca-certificates \
  python3.11 python3.11-venv python3.11-dev python3-pip \
  build-essential nodejs npm

# --- 2. Создание пользователя и директорий ---------------------------------
if ! id -u "$APP_USER" >/dev/null 2>&1; then
  useradd --system --create-home --home-dir "$INSTALL_DIR" --shell /usr/sbin/nologin "$APP_USER"
  green "    создан системный пользователь ${APP_USER}"
fi

mkdir -p "$INSTALL_DIR" "$DATA_DIR" "$LOG_DIR"

# --- 3. Клонирование или обновление приложения ------------------------------
if [ -d "$INSTALL_DIR/.git" ]; then
  yellow "    обновление существующей копии..."
  git -C "$INSTALL_DIR" fetch origin
  git -C "$INSTALL_DIR" reset --hard "origin/$(git -C "$INSTALL_DIR" rev-parse --abbrev-ref HEAD)"
else
  yellow "    клонирование репозитория..."
  rm -rf "$INSTALL_DIR"
  git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
fi

chown -R "${APP_USER}:${APP_GROUP}" "$INSTALL_DIR" "$DATA_DIR" "$LOG_DIR"

# --- 4. Настройка .env ------------------------------------------------------
ENV_FILE="$INSTALL_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
  cp "$INSTALL_DIR/.env.example" "$ENV_FILE"
  green "    создан .env из .env.example"
else
  yellow "    .env уже существует — сохраняем значения, заполняем пустые поля"
fi

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

env_get() {
  local key="$1"
  [ -f "$ENV_FILE" ] || { echo ""; return; }
  sed -n "s/^${key}=//p" "$ENV_FILE" | head -n1
}

ensure_var() {
  local key="$1" value="$2"
  [ -z "$(env_get "$key")" ] && env_set "$key" "$value"
}

ensure_var JWT_SECRET_KEY "$(gen_secret)"
ensure_var CACHE_SIGNING_KEY "$(gen_secret)"
ensure_var BOOTSTRAP_ADMIN_EMAIL "admin@openterminal.local"

ADMIN_PASS="$(env_get BOOTSTRAP_ADMIN_PASSWORD)"
if [ -z "$ADMIN_PASS" ]; then
  ADMIN_PASS="$(gen_secret | cut -c1-20)"
  env_set BOOTSTRAP_ADMIN_PASSWORD "$ADMIN_PASS"
fi
ADMIN_EMAIL="$(env_get BOOTSTRAP_ADMIN_EMAIL)"

# Пути данных под управлением сервиса
env_set OPENTERMINALUI_SQLITE_URL "sqlite:///${DATA_DIR}/openterminalui.db"
env_set DATABASE_URL "sqlite+aiosqlite:///${DATA_DIR}/openterminal.db"
env_set REDIS_URL ""

chown "${APP_USER}:${APP_GROUP}" "$ENV_FILE"
chmod 640 "$ENV_FILE"

# --- 5. Установка Python-зависимостей и сборка frontend ---------------------
yellow "    установка Python-зависимостей..."
sudo -u "$APP_USER" python3.11 -m venv "$INSTALL_DIR/.venv"
sudo -u "$APP_USER" "$INSTALL_DIR/.venv/bin/pip" install --quiet --upgrade pip
sudo -u "$APP_USER" "$INSTALL_DIR/.venv/bin/pip" install --quiet -r "$INSTALL_DIR/backend/requirements.txt"

yellow "    сборка frontend..."
sudo -u "$APP_USER" bash -c "cd '$INSTALL_DIR/frontend' && npm ci && npm run build"

# --- 6. Миграции и создание администратора ----------------------------------
yellow "    выполнение миграций базы данных..."
sudo -u "$APP_USER" bash -c "cd '$INSTALL_DIR' && PYTHONPATH='$INSTALL_DIR' '$INSTALL_DIR/.venv/bin/python' -m alembic -c '$INSTALL_DIR/backend/alembic.ini' upgrade head" || true

yellow "    создание учётной записи администратора..."
sudo -u "$APP_USER" bash -c "cd '$INSTALL_DIR' && PYTHONPATH='$INSTALL_DIR' '$INSTALL_DIR/.venv/bin/python' '$INSTALL_DIR/scripts/seed_admin.py'"

# --- 7. Установка systemd-сервиса ------------------------------------------
yellow "    установка systemd-сервиса ${SERVICE_NAME}..."
cp "$INSTALL_DIR/scripts/openterminalui.service" "/etc/systemd/system/${SERVICE_NAME}"
sed -i "s|{{INSTALL_DIR}}|${INSTALL_DIR}|g" "/etc/systemd/system/${SERVICE_NAME}"
sed -i "s|{{DATA_DIR}}|${DATA_DIR}|g" "/etc/systemd/system/${SERVICE_NAME}"
sed -i "s|{{LOG_DIR}}|${LOG_DIR}|g" "/etc/systemd/system/${SERVICE_NAME}"
sed -i "s|{{PORT}}|${PORT}|g" "/etc/systemd/system/${SERVICE_NAME}"
sed -i "s|{{APP_USER}}|${APP_USER}|g" "/etc/systemd/system/${SERVICE_NAME}"
sed -i "s|{{APP_GROUP}}|${APP_GROUP}|g" "/etc/systemd/system/${SERVICE_NAME}"

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

# --- 8. Запуск сервиса ------------------------------------------------------
yellow "    запуск сервиса..."
systemctl restart "$SERVICE_NAME"

sleep 3
if systemctl is-active --quiet "$SERVICE_NAME"; then
  green "    сервис ${SERVICE_NAME} успешно запущен"
else
  red "    ошибка запуска сервиса ${SERVICE_NAME}"
  systemctl status "$SERVICE_NAME" --no-pager
  exit 1
fi

# --- 9. Вывод учётных данных ------------------------------------------------
echo
green "============================================================"
green " OpenTerminalUI готов -> http://localhost:${PORT}"
green "------------------------------------------------------------"
green "  Войдите, используя:"
green "    email:    ${ADMIN_EMAIL}"
green "    password: ${ADMIN_PASS}"
green "  (также сохранено в ${ENV_FILE}; смените пароль после первого входа)"
green "============================================================"
echo
cyan "  Управление сервисом:"
cyan "    systemctl status ${SERVICE_NAME}"
cyan "    systemctl stop ${SERVICE_NAME}"
cyan "    systemctl restart ${SERVICE_NAME}"
cyan "    systemctl disable ${SERVICE_NAME}"
