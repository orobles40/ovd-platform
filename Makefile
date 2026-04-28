.PHONY: lint lint-check format test test-unit test-cov pre-commit-install

ENGINE := src/engine
PYTHON := $(ENGINE)/.venv/bin/python
RUFF   := $(ENGINE)/.venv/bin/ruff
PYTEST := $(ENGINE)/.venv/bin/pytest

# Lint + auto-fix
lint:
	cd $(ENGINE) && $(RUFF) check . --fix
	cd $(ENGINE) && $(RUFF) format .

# Solo verificar sin modificar (para CI manual)
lint-check:
	cd $(ENGINE) && $(RUFF) check . --no-fix
	cd $(ENGINE) && $(RUFF) format . --check

# Solo formatear
format:
	cd $(ENGINE) && $(RUFF) format .

# Tests sin infraestructura (default)
test:
	cd $(ENGINE) && $(PYTEST) tests/ -m "not integration and not docker" -v

# Solo unit tests
test-unit:
	cd $(ENGINE) && $(PYTEST) tests/ -m unit -v

# Tests con coverage HTML
test-cov:
	cd $(ENGINE) && $(PYTEST) tests/ --cov=. --cov-report=html \
	    -m "not integration and not docker" -q
	@echo "Reporte: $(ENGINE)/htmlcov/index.html"

# Instalar pre-commit hooks
pre-commit-install:
	pre-commit install
