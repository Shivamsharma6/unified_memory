.PHONY: install start stop restart status migrate doctor integrate logs test test-unit test-integration dev-up dev-down lint embed-upgrade evaluate clean

VENV = memory_watcher/.venv
PYTHON = PYTHONPATH=.:memory_watcher $(VENV)/bin/python
PIP = $(VENV)/bin/pip

install:
	@echo "Creating virtual environment..."
	python3 -m venv $(VENV)
	@echo "Installing memory_watcher dependencies..."
	$(PIP) install -r memory_watcher/requirements.txt
	@echo "Installing uams_sdk..."
	$(PIP) install -e ./uams_sdk
	@echo "Installation complete!"

dev-up:
	@echo "Starting PostgreSQL and Qdrant development infrastructure..."
	docker compose -f memory_watcher/docker-compose.yml up -d --wait postgres qdrant

dev-down:
	@echo "Stopping PostgreSQL and Qdrant development infrastructure..."
	docker compose -f memory_watcher/docker-compose.yml down

start:
	./uams start

stop:
	./uams stop

restart:
	./uams restart

status:
	./uams status

migrate:
	./uams migrate

embed-upgrade:
	./uams embed-upgrade

doctor:
	./uams doctor

integrate:
	./uams integrate

lint:
	@echo "Linting memory vault..."
	./uams lint

logs:
	./uams logs

test:
	@echo "Running all memory_watcher tests..."
	$(PYTHON) -m pytest memory_watcher/tests/
	@echo "Running uams_sdk tests..."
	$(PYTHON) -m pytest uams_sdk/tests/

test-unit:
	@echo "Running unit tests (excluding live container integration)..."
	$(PYTHON) -m pytest memory_watcher/tests/ -m "not integration"
	@echo "Running uams_sdk unit tests..."
	$(PYTHON) -m pytest uams_sdk/tests/

test-integration:
	$(PYTHON) -m pytest memory_watcher/tests/integration/ -v

evaluate:
	$(PYTHON) memory_watcher/scripts/evaluate_retrieval.py --require-hit1 0.80 --require-hit5 0.90

clean:
	./uams stop
	rm -rf $(VENV)
	rm -rf uams_sdk/*.egg-info
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +

