PYTHON ?= $(shell if [ -x ./.venv/bin/python ]; then printf '%s' ./.venv/bin/python; elif command -v python >/dev/null 2>&1; then printf '%s' python; else printf '%s' python3; fi)
SRC_DIR := src
PACKAGE_DIR := $(SRC_DIR)/anki_slot_machine
PYTHON_SOURCES := $(shell find $(SRC_DIR) -name '*.py' | sort)
DEV_VERSION := 0.0.0-dev.$(shell date -u +%Y%m%d%H%M%S)
VERSION ?= $(DEV_VERSION)
PYCACHE_PREFIX := /tmp/anki-slot-machine-pyc

.DEFAULT_GOAL := help
.PHONY: help build install install-hooks install-dev lint format check test real-slot-report real-slot-plot clean

help:
	@printf '%s\n' \
		'Available targets:' \
		'  make build          Build the .ankiaddon archive (default: dev version)' \
		'  make install        Build and install into your local Anki addons21 folder' \
		'  make install-hooks  Enable the repo pre-commit hook' \
		'  make install-dev    Install pinned Python dev dependencies' \
		'  make lint           Run black in check mode' \
		'  make format         Format Python files with black' \
		'  make check          Compile Python sources to catch syntax errors' \
		'  make test           Run the unit test suite' \
		'  make real-slot-report  Evaluate a real slot from faces + fixed gains' \
		'  make real-slot-plot    Plot a real slot from faces + fixed gains' \
		'  make clean          Remove build artifacts and local caches' \
		'' \
		'Variables:' \
		'  VERSION=x.y.z       Override the generated dev version for build/install'

build:
	./build.sh "$(VERSION)"

install:
	./install.sh "$(VERSION)"

install-hooks:
	git config core.hooksPath .githooks

install-dev:
	$(PYTHON) -m pip install -r requirements-dev.txt

lint:
	$(PYTHON) -m black --check $(SRC_DIR)

format:
	$(PYTHON) -m black $(SRC_DIR)

check:
	PYTHONPYCACHEPREFIX=$(PYCACHE_PREFIX) $(PYTHON) -m py_compile $(PYTHON_SOURCES)

test:
	PYTHONPATH=$(SRC_DIR) $(PYTHON) -m unittest discover -s tests -v
	node tests/test_slot_machine_layout_smoke.mjs

real-slot-report:
	$(PYTHON) scripts/evaluate_real_slot.py

real-slot-plot:
	PYTHONPATH=scripts $(PYTHON) scripts/plot_real_slot.py

clean:
	rm -rf dist
	find $(PACKAGE_DIR) -type d -name '__pycache__' -prune -exec rm -rf {} +
	find $(PACKAGE_DIR) -type f -name '*.pyc' -delete
