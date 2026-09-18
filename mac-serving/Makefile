.PHONY: bootstrap plan doctor serve test benchmark

PYTHON := .venv/bin/python

bootstrap:
	./scripts/bootstrap.sh

plan:
	$(PYTHON) -m mac_serving plan

doctor:
	$(PYTHON) -m mac_serving doctor

serve:
	$(PYTHON) -m mac_serving serve

test:
	$(PYTHON) -m pytest

benchmark:
	$(PYTHON) -m mac_serving benchmark --requests 8 --concurrency 2
