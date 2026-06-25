#!/usr/bin/env bash
# ============================================================================
# OpenTerminalUI — удаление установки из Debian/Ubuntu.
#
#   sudo ./scripts/uninstall-debian.sh
# ============================================================================
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Ошибка: этот скрипт должен запускаться от root (используйте sudo)." >&2
  exit 1
fi

APP_NAME="openterminalui"
APP_USER="openterminalui"
INSTALL_DIR="/opt/${APP_NAME}"
DATA_DIR="/var/lib/${APP_NAME}"
LOG_DIR="/var/log/${APP_NAME}"
SERVICE_NAME="${APP_NAME}.service"

read -rp "Удалить OpenTerminalUI, данные (${DATA_DIR}) и сервис? [y/N]: " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
  echo "Отменено."
  exit 0
fi

systemctl stop "$SERVICE_NAME" 2>/dev/null || true
systemctl disable "$SERVICE_NAME" 2>/dev/null || true
rm -f "/etc/systemd/system/${SERVICE_NAME}"
systemctl daemon-reload

userdel "$APP_USER" 2>/dev/null || true
rm -rf "$INSTALL_DIR" "$LOG_DIR"

read -rp "Удалить базы данных в ${DATA_DIR}? [y/N]: " remove_data
if [[ "$remove_data" =~ ^[Yy]$ ]]; then
  rm -rf "$DATA_DIR"
fi

echo "OpenTerminalUI удалён."
