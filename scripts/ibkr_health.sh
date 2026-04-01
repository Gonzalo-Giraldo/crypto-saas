cat > scripts/ibkr_health.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

echo "[runtime pid]"
ps aux | grep ibkr_persistent_runtime.py | grep -v grep || true
echo
echo "[bridge pid]"
ps aux | grep "uvicorn ibkr_runtime_bridge:app" | grep -v grep || true
echo
echo "[runtime status]"
cat /tmp/ibkr_runtime_status.json || true
echo
echo "[bridge health]"
curl -i -sS http://127.0.0.1:8015/health || true
echo
echo "[account status]"
curl -i -sS http://127.0.0.1:8015/ibkr/paper/account-status || true
echo
echo "[command]"
cat /tmp/ibkr_runtime_command.json 2>/dev/null || true
echo
echo "[result]"
cat /tmp/ibkr_runtime_result.json 2>/dev/null || true
EOF
chmod +x scripts/ibkr_health.sh
