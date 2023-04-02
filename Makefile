.PHONY: install run lint help
.DEFAULT_GOAL := help

install: ## Install requirements
	python3 -m pip install -r requirements.txt

run: ## Run project
	gunicorn -b 127.0.0.1:5000 --log-level debug app:app

lint: ## Lint files
	find . -name "*.py" | xargs python3 -m pylint --rcfile=.pylintrc

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' Makefile | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

