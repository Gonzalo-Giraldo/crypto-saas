IMAGE=minimal-core-py311-check
PROJECT_ROOT=$(PWD)

.PHONY: help build test validate-api validate-gateway validate clean-idempotency

help:
	@echo "Targets:"
	@echo "  make build"
	@echo "  make test"
	@echo "  make validate-api"
	@echo "  make validate-gateway"
	@echo "  make validate"
	@echo "  make clean-idempotency"

clean-idempotency:
	rm -f "$(PROJECT_ROOT)/.minimal_runtime_idempotency_store.json"
	rm -f "$(PROJECT_ROOT)/apps/.minimal_runtime_idempotency_store.json"

build:
	docker build -t $(IMAGE) .

test:
	docker run --rm -e PYTHONPATH=/app -w /app $(IMAGE) pytest -q tests/test_minimal_core_baseline.py

validate-api:
	curl -fsS https://crypto-saas-znhb.onrender.com/ > /dev/null
	curl -fsS https://crypto-saas-znhb.onrender.com/health
	curl -fsS https://crypto-saas-znhb.onrender.com/healthz

validate-gateway:
	curl -fsS https://crypto-saas-binance-gateway-01.onrender.com/healthz

validate: build test validate-api validate-gateway
