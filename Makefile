.PHONY: install start stop restart logs test clean

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

logs:
	./uams logs

test:
	@echo "Running memory_watcher tests..."
	$(PYTHON) -m pytest memory_watcher/tests/
	@echo "Running uams_sdk tests..."
	$(PYTHON) -m pytest uams_sdk/tests/

clean:
	./uams stop
	rm -rf $(VENV)
	rm -rf uams_sdk/*.egg-info
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
