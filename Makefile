.PHONY: help install lint format typecheck test check build run compose-up compose-down clean

IMAGE ?= paperless-paddle-ocr:dev

help:
	@echo "Targets: install lint format typecheck test check build run compose-up compose-down clean"

install:
	pip install -r requirements-dev.txt

lint:
	ruff check .

format:
	ruff format .

typecheck:
	mypy ocr_worker.py

test:
	pytest -v

check: lint typecheck test

build:
	docker build -t $(IMAGE) .

run: build
	docker run --rm --env-file .env -p 8081:8080 $(IMAGE)

compose-up:
	docker compose up -d --build

compose-down:
	docker compose down

clean:
	find . -name '__pycache__' -exec rm -rf {} +
	rm -rf .mypy_cache .ruff_cache .pytest_cache
