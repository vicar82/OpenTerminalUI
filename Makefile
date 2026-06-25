SHELL := /bin/bash

.PHONY: install up keys seed-admin setup setup-backend setup-frontend test test-backend build build-frontend gate

# Установка и запуск в локальном режиме.
install up:
	./install.sh

# Интерактивный мастер настройки API-ключей в .env.
keys:
	./scripts/setup-keys.sh

# Создание начальной учётной записи администратора (идемпотентно).
seed-admin:
	PYTHONPATH=. python scripts/seed_admin.py

setup: setup-backend setup-frontend

setup-backend:
	python3 -m venv .venv && source .venv/bin/activate && pip install -r backend/requirements.txt && pip install pytest

setup-frontend:
	cd frontend && npm install

test: test-backend

test-backend:
	PYTHONPATH=. python -m compileall backend && PYTHONPATH=. pytest backend/tests -q

build: build-frontend

build-frontend:
	cd frontend && npm run build

gate: test-backend build-frontend
