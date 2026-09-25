.DEFAULT_GOAL := help

PYTHON ?= python3
VENV := .venv
BIN := $(VENV)/bin
COMPOSE := docker compose --env-file .env
APP_HOST ?= 127.0.0.1
APP_PORT ?= 8000

.PHONY: help install dev start test docker docker-build docker-up docker-down docker-logs docker-ps docker-restart

help:
	@echo "Pingwatch"
	@echo
	@echo "  make install         Create .venv and install Python deps"
	@echo "  make dev             Run the API with reload (host)"
	@echo "  make start           Run the API without reload (host)"
	@echo "  make test            Run pytest"
	@echo "  make docker-build    Build the web image"
	@echo "  make docker / docker-up   Build and start Compose in the background"
	@echo "  make docker-logs     Follow web and mysql logs"
	@echo "  make docker-ps       Show Compose service status"
	@echo "  make docker-restart  Restart the web service"
	@echo "  make docker-down     Stop containers (keeps volumes)"

$(BIN)/pip:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip

install: $(BIN)/pip
	$(BIN)/pip install -r requirements.txt

dev: $(BIN)/pip
	$(BIN)/uvicorn app.main:app --reload --host $(APP_HOST) --port $(APP_PORT)

start: $(BIN)/pip
	$(BIN)/uvicorn app.main:app --host 0.0.0.0 --port $(APP_PORT) --proxy-headers --forwarded-allow-ips '*' --timeout-graceful-shutdown 20

test: $(BIN)/pip
	$(BIN)/pytest -q

.env:
	@test -f .env || (echo "Missing .env — copy .env.example to .env and set secrets." >&2; exit 1)

docker-build: .env
	$(COMPOSE) build --pull

docker docker-up: .env
	$(COMPOSE) up --build -d --remove-orphans
	$(COMPOSE) ps

docker-logs: .env
	$(COMPOSE) logs -f --tail=200

docker-ps: .env
	$(COMPOSE) ps

docker-restart: .env
	$(COMPOSE) restart web

docker-down: .env
	$(COMPOSE) down --remove-orphans
