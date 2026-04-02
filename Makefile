.PHONY: test install lint-self test-cov clean rules pipenv virtualenv

test:
	python -m pytest -q

# Auto-detect: prefer .venv, fall back to pipenv
install:
	@if [ -d .venv ]; then \
	  .venv/bin/pip install -r requirements.txt; \
	elif command -v pipenv > /dev/null 2>&1; then \
	  pipenv install; \
	else \
	  echo "No .venv found and pipenv not available. Run 'make virtualenv' or 'make pipenv' first."; \
	  exit 1; \
	fi

# Pipenv environment (uses Pipfile)
pipenv:
	pipenv install --dev
	pipenv run python -m spacy download en_core_web_sm

# Standard .venv environment (uses requirements.txt)
virtualenv:
	python -m venv .venv
	.venv/bin/pip install -r requirements.txt
	.venv/bin/python -m spacy download en_core_web_sm

lint-self:
	-rhetoric-lint --format text docs/ README.md

test-cov:
	python -m pytest --cov=rhetoric_lint --cov-report=term-missing -q

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; \
	find . -name "*.pyc" -delete; \
	rm -rf .pytest_cache .coverage

rules:
	rhetoric-lint rules
