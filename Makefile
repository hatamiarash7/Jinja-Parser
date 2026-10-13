export PYTHONDONTWRITEBYTECODE := 1
export PYTHONUNBUFFERED := 1

# Override with: make <target> PYTHON=.venv/bin/python
PYTHON ?= python3

APP_FILES := app.py test_app.py

.PHONY: install install-dev run run-dev lint test coverage check clean docker-build docker-run help
.DEFAULT_GOAL := help

install: ## Install runtime requirements
	$(PYTHON) -m pip install -r requirements.txt

install-dev: ## Install runtime + development requirements
	$(PYTHON) -m pip install -r requirements-dev.txt

run: ## Run the production server (gunicorn on 127.0.0.1:5000)
	$(PYTHON) -m gunicorn --bind 127.0.0.1:5000 --workers 2 --timeout 30 --log-level info app:app

run-dev: ## Run the development server (auto-reload on http://127.0.0.1:5000)
	$(PYTHON) -m flask --app app run --debug --host 127.0.0.1 --port 5000

lint: ## Lint project files
	$(PYTHON) -m pylint --rcfile=.pylintrc $(APP_FILES)

test: ## Run tests with coverage report
	$(PYTHON) -m pytest -v --cov=app --cov-report=term-missing

coverage: ## Run tests and write coverage report to htmlcov/index.html
	$(PYTHON) -m pytest --cov=app --cov-report=html
	@echo "Coverage report: htmlcov/index.html"

check: lint test ## Run lint + tests

clean: ## Remove caches and build artifacts
	rm -rf __pycache__ .pytest_cache htmlcov .coverage
	find . -path ./.venv -prune -o -name "__pycache__" -type d -print | xargs rm -rf

docker-build: ## Build the Docker image locally
	docker build -t hatamiarash7/jinja-parser:local .

docker-run: ## Run the local Docker image on http://localhost:8125
	docker run --rm -p 8125:8125 hatamiarash7/jinja-parser:local

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' Makefile | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'
