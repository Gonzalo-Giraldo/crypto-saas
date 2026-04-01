<<'EOF'
# IBKR Execution Runbook (Minimal S2S)

## Objetivo
Garantizar ejecución confiable:

bridge -> runtime -> IBKR

---

## 1. STOP SEQUENCE

```bash
pkill -f "uvicorn ibkr_runtime_bridge:app" || true
pkill -f "ibkr_persistent_runtime.py" || true
sleep 2


# 🧭 IBKR Execution Runbook (Minimal S2S)

## 🎯 Objetivo

Garantizar ejecución confiable:

```
bridge → runtime → IBKR
```

---

## 1. STOP SEQUENCE

```bash
pkill -f "uvicorn ibkr_runtime_bridge:app" || true
pkill -f "ibkr_persistent_runtime.py" || true
sleep 2
```

Validar:

```bash
ps aux | grep "uvicorn ibkr_runtime_bridge:app" | grep -v grep
ps aux | grep ibkr_persistent_runtime.py | grep -v grep
```

👉 Debe NO haber procesos.

---

## 2. IBKR SESSION RESET

Si aparece error:

```
clientId already in use
```

👉 Acción obligatoria:

* reiniciar TWS o IB Gateway
* esperar 10–15s

---

## 3. START SEQUENCE

### 3.1 Runtime

```bash
python3 ibkr_persistent_runtime.py
```

Esperado:

```
connected=True
```

---

### 3.2 Runtime Health

```bash
cat /tmp/ibkr_runtime_status.json
```

Debe contener:

```json
"connected": true
```

---

### 3.3 Bridge

```bash
python3 -m uvicorn ibkr_runtime_bridge:app --host 0.0.0.0 --port 8015
```

---

### 3.4 Bridge Health

```bash
curl -i -sS http://127.0.0.1:8015/health
curl -i -sS http://127.0.0.1:8015/ibkr/paper/account-status
```

---

## 4. TEST ORDER (EXECUTION CHECK)

```bash
curl -i -sS -X POST http://127.0.0.1:8015/ibkr/paper/test-order \
  -H "Content-Type: application/json" \
  -d '{"symbol":"AAPL","side":"BUY","qty":1,"order_ref":"runbook-test-001"}'
```

---

## 5. S2S EVIDENCE

```bash
printf '\n===== command =====\n'
cat /tmp/ibkr_runtime_command.json 2>/dev/null || true

printf '\n===== result =====\n'
cat /tmp/ibkr_runtime_result.json 2>/dev/null || true
```

---

## 6. EXPECTED BEHAVIOR

### ✅ Correcto

* HTTP 200
* `success: true`
* `order_id` presente
* `status`: PendingSubmit / Submitted / Filled

### ❌ Errores conocidos

| Error                 | Causa                      |
| --------------------- | -------------------------- |
| 501                   | bridge viejo               |
| 504 timeout           | runtime no consume command |
| clientId in use       | sesión IBKR no liberada    |
| runtime_not_running   | proceso no activo          |
| runtime_not_connected | IBKR desconectado          |

---

## 7. INVARIANTES (NO NEGOCIABLES)

* `client_id = 1` (no cambiar)
* una sola instancia de runtime
* una sola instancia de bridge
* sin simulación
* sin reconexión en test-order
* trazabilidad por `request_id`

---

## 8. CHECK FINAL

Antes de cualquier cambio en execution:

* [ ] runtime activo
* [ ] bridge activo
* [ ] IBKR conectado
* [ ] health endpoints OK
* [ ] single-instance verificado
* [ ] test-order responde

---

## 🧠 Nota operativa clave

Este sistema **no es stateless**.
Siempre tratar como:

```
infra + proceso + sesión externa (IBKR)
```

No operar como script local.

