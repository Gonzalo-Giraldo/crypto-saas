#!/usr/bin/env bash
set -euo pipefail

pkill -f "uvicorn ibkr_runtime_bridge:app" || true
pkill -f "ibkr_persistent_runtime.py" || true
sleep 2

echo "[bridge]"
ps aux | grep "uvicorn ibkr_runtime_bridge:app" | grep -v grep || true

echo "[runtime]"
ps aux | grep "ibkr_persistent_runtime.py" | grep -v grep || true
