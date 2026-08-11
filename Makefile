.PHONY: install start stop restart status migrate doctor integrate logs test test-integration evaluate clean

VENV = memory_watcher/.venv
PYTHON = $(VENV)/bin/python
PIP = $(VENV)/bin/pip

install:
	@echo "Creating virtual environment..."
	python3 -m venv $(VENV)
	@echo "Installing memory_watcher dependencies..."
	$(PIP) install -r memory_watcher/requirements.txt
	@echo "Installing uams_sdk..."
	$(PIP) install -e ./uams_sdk
	@echo "Installation complete!"

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

doctor:
	./uams doctor

integrate:
	./uams integrate

logs:
	./uams logs

test:
	@echo "Running memory_watcher tests..."
	$(PYTHON) -m pytest memory_watcher/tests/
	@echo "Running uams_sdk tests..."
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
