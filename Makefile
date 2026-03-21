IMAGE=minimal-core-py311-check

.PHONY: test build

build:
	docker build -t $(IMAGE) .

test:
	docker run --rm -e PYTHONPATH=/app -w /app $(IMAGE) pytest -q tests/test_minimal_core_baseline.py
