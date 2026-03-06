# Runbook de Validacion (Post-Deploy)

Objetivo: validar extremo a extremo los modulos criticos implementados:
- `market-monitor` (incluye MTF 1D/4H/1H),
- `auto-pick` (incluye columnas de tendencia top-candidate),
- `learning pipeline` (dataset, label, rollup),
- vista `/ops/console`.

## 1) Sesion admin

```bash
export BASE_URL="https://TU_API"
export ADMIN_EMAIL="tu_admin@dominio.com"
export ADMIN_PASSWORD="tu_password"
```

Login:

```bash
curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=$ADMIN_EMAIL" \
  -d "password=$ADMIN_PASSWORD" | python3 -m json.tool
```

Si responde `{"detail":"OTP required"}`, usar OTP:

```bash
read "OTP?OTP: "
export ADMIN_TOKEN=$(
  curl -s -X POST "$BASE_URL/auth/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=$ADMIN_EMAIL" \
    -d "password=$ADMIN_PASSWORD" \
    -d "otp=$OTP" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin).get("access_token",""))'
)
```

## 2) Health

```bash
curl -s "$BASE_URL/healthz" | python3 -m json.tool
```

Debe responder `{"status":"ok"}`.

## 3) Market monitor (MTF + fallback)

Forzar tick:

```bash
curl -s -X POST "$BASE_URL/ops/admin/market-monitor/tick" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool
```

Consultar reporte:

```bash
curl -s "$BASE_URL/ops/admin/market-monitor/report?hours=1&limit=100&exchange=BINANCE" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool
```

Esperado:
- filas con `source="klines_1h_mtf"` cuando hay datos de klines,
- posible mezcla con `source="ticker_24h_fallback"` en ventanas de fallback,
- campos `trend_score`, `momentum_score`, `atr_pct`, `confidence`.

## 4) Auto-pick (admin tick + reporte)

Tick:

```bash
curl -s -X POST "$BASE_URL/ops/admin/auto-pick/tick?dry_run=true&top_n=10&real_only=true&include_service_users=false" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool
```

Validar que salgan campos:
- `selected_trend_score`, `selected_trend_score_1d`, `selected_trend_score_4h`, `selected_trend_score_1h`
- `top_candidate_trend_score`, `top_candidate_trend_score_1d`, `top_candidate_trend_score_4h`, `top_candidate_trend_score_1h`

Reporte:

```bash
curl -s "$BASE_URL/ops/admin/auto-pick/report?hours=2&limit=200&interval_minutes=5" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool
```

Filtro rapido de tendencias:

```bash
curl -s "$BASE_URL/ops/admin/auto-pick/report?hours=2&limit=200&interval_minutes=5" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
| python3 -c 'import sys,json; d=json.load(sys.stdin); [print(r.get("timestamp"), r.get("exchange"), r.get("symbol"), "trend=", r.get("top_candidate_trend_score"), "1d=", r.get("top_candidate_trend_score_1d"), "4h=", r.get("top_candidate_trend_score_4h"), "1h=", r.get("top_candidate_trend_score_1h")) for r in d.get("rows", [])[:20]]'
```

## 5) Learning pipeline

Status:

```bash
curl -s "$BASE_URL/ops/admin/learning/status" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool
```

Dataset:

```bash
curl -s "$BASE_URL/ops/admin/learning/dataset?hours=6&limit=200&outcome_status=ALL&exchange=ALL" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool
```

Label:

```bash
curl -s -X POST "$BASE_URL/ops/admin/learning/label?dry_run=false&horizon_minutes=60&limit=500" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool
```

Rollup refresh:

```bash
curl -s -X POST "$BASE_URL/ops/admin/learning/rollup/refresh?hours=72&dry_run=false" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool
```

Rollup report:

```bash
curl -s "$BASE_URL/ops/admin/learning/rollup?hours=72&limit=500&exchange=ALL" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool
```

## 6) Validacion UI `/ops/console`

1. Abrir `https://TU_API/ops/console`.
2. Login con admin.
3. Ir a `Auto-pick Report`.
4. Clic en `Cargar ahora`.
5. Confirmar columnas:
   - `Tendencia`
   - `MTF 1D/4H/1H`

Si no aparecen:
- hacer hard refresh (`Cmd+Shift+R`),
- volver a cargar reporte.

## 7) Criterio de pase

- `healthz` en `ok`.
- `market-monitor` devuelve filas recientes.
- `auto-pick` devuelve tendencias selected/top-candidate.
- `learning` responde status/dataset/label/rollup sin `Not Found`.
- `/ops/console` refleja columnas nuevas de tendencia.
