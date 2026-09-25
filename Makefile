.PHONY: install dev start test docker docker-down

install:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt

dev:
	.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

start:
	.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --timeout-graceful-shutdown 15

test:
	.venv/bin/pytest -q

docker:
	docker compose up --build

docker-down:
	docker compose down
