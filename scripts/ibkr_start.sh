cat > scripts/ibkr_start.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/user/Documents/New project 4"
RUNTIME_LOG="/tmp/ibkr_runtime.log"
BRIDGE_LOG="/tmp/ibkr_bridge.log"

cd "$ROOT"

if pgrep -f "ibkr_persistent_runtime.py" >/dev/null 2>&1; then
  echo "runtime already running"
  exit 1
fi

if pgrep -f "uvicorn ibkr_runtime_bridge:app" >/dev/null 2>&1; then
  echo "bridge already running"
  exit 1
fi

nohup python3 ibkr_persistent_runtime.py > "$RUNTIME_LOG" 2>&1 &
sleep 3

if ! pgrep -f "ibkr_persistent_runtime.py" >/dev/null 2>&1; then
  echo "runtime failed"
  tail -n 50 "$RUNTIME_LOG" || true
  exit 1
fi

nohup python3 -m uvicorn ibkr_runtime_bridge:app --host 0.0.0.0 --port 8015 --log-level debug > "$BRIDGE_LOG" 2>&1 &
sleep 2

if ! pgrep -f "uvicorn ibkr_runtime_bridge:app" >/dev/null 2>&1; then
  echo "bridge failed"
  tail -n 50 "$BRIDGE_LOG" || true
  exit 1
fi

cat /tmp/ibkr_runtime_status.json || true
printf '\n'
curl -i -sS http://127.0.0.1:8015/health || true
printf '\n'
curl -i -sS http://127.0.0.1:8015/ibkr/paper/account-status || true
printf '\n'
EOF
chmod +x scripts/ibkr_start.sh
