PYTHON ?= $(shell if [ -x ./.venv/bin/python ]; then printf '%s' ./.venv/bin/python; else printf '%s' python3; fi)
PACKAGE := src/anki_slot_machine
PYTHON_SOURCES := $(shell find src -name '*.py' | sort)

.PHONY: help build install lint format check test real-slot-report real-slot-plot clean

DEV_VERSION := 0.0.0-dev.$(shell date -u +%Y%m%d%H%M%S)

help:
	@printf '%s\n' \
		'Available targets:' \
		'  make build    Build the .ankiaddon archive (override with VERSION=x.y.z)' \
		'  make install  Build and install into your local Anki addons21 folder (override with VERSION=x.y.z)' \
		'  make lint     Run black in check mode' \
		'  make format   Format Python files with black' \
		'  make check    Compile Python sources to catch syntax errors' \
		'  make test     Run the unit test suite' \
		'  make real-slot-report  Evaluate a real slot from faces + fixed gains' \
		'  make real-slot-plot    Plot a real slot from faces + fixed gains' \
		'  make clean    Remove build artifacts and local caches'

build:
	./build.sh "$(or $(VERSION),$(DEV_VERSION))"

install:
	./install.sh "$(or $(VERSION),$(DEV_VERSION))"

lint:
	$(PYTHON) -m black --check src

format:
	$(PYTHON) -m black src

check:
	PYTHONPYCACHEPREFIX=/tmp/anki-slot-machine-pyc $(PYTHON) -m py_compile $(PYTHON_SOURCES)

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v
	node tests/test_slot_machine_layout_smoke.mjs

real-slot-report:
	$(PYTHON) scripts/evaluate_real_slot.py

real-slot-plot:
	PYTHONPATH=scripts $(PYTHON) scripts/plot_real_slot.py

clean:
	rm -rf dist
	find $(PACKAGE) -type d -name '__pycache__' -prune -exec rm -rf {} +
	find $(PACKAGE) -type f -name '*.pyc' -delete
