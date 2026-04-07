PYTHON ?= $(shell if [ -x ./.venv/bin/python ]; then printf '%s' ./.venv/bin/python; else printf '%s' python3; fi)
PACKAGE := src/anki_slot_machine
PYTHON_SOURCES := $(shell find src -name '*.py' | sort)

.PHONY: help build install lint format check test solver clean

help:
	@printf '%s\n' \
		'Available targets:' \
		'  make build    Build the .ankiaddon archive' \
		'  make install  Build and install into your local Anki addons21 folder' \
		'  make lint     Run black in check mode' \
		'  make format   Format Python files with black' \
		'  make check    Compile Python sources to catch syntax errors' \
		'  make test     Run the unit test suite' \
		'  make solver   Print the slot EV solver breakdown from config.json' \
		'  make clean    Remove build artifacts and local caches'

build:
	./build.sh

install:
	./install.sh

lint:
	$(PYTHON) -m black --check src

format:
	$(PYTHON) -m black src

check:
	$(PYTHON) -m py_compile $(PYTHON_SOURCES)

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v

solver:
	PYTHONPATH=src $(PYTHON) scripts/show_slot_solver.py

clean:
	rm -rf dist
	find $(PACKAGE) -type d -name '__pycache__' -prune -exec rm -rf {} +
	find $(PACKAGE) -type f -name '*.pyc' -delete
