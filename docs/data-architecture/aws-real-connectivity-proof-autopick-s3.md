# AWS Real Connectivity Proof — Auto-pick DATA Export Plane

## Objetivo

Realizar una prueba controlada y manual de conectividad AWS/S3 para validar:

* resolución real de credenciales,
* conectividad S3 real,
* permisos IAM mínimos,
* upload real,
* metadata real,
* checksum remoto,
* head verification real,
* encryption contract,
* y boundary fail-closed.

Sin:

* scheduler,
* retries,
* purge,
* replay automation,
* runtime coupling,
* broker access,
* trading,
* lifecycle automation.

---

# Estado previo confirmado

Substrate ya implementado:

```text
rows
→ deterministic JSONL
→ deterministic checksum
→ storage abstraction
→ disk/s3 routing
→ manifest artifact
→ remote verification
→ fail-closed config validation
→ lifecycle persistence
```

Commits relevantes:

```text
556581d Add fail-closed S3 autopick export storage adapter
997ed08 Route autopick export batch through storage adapters
df60abc Harden S3 autopick export configuration validation
```

Tests verdes:

```text
21 passed
```

---

# Objetivo del connectivity proof

NO probar scheduler.
NO probar lifecycle automation.
NO probar producción completa.
NO probar workers.
NO probar replay.

Solo demostrar:

```text
python process
→ boto3
→ AWS credentials
→ S3 put_object
→ S3 head_object
→ metadata integrity
→ checksum integrity
→ encryption contract
```

---

# Script propuesto

Ruta:

```text
scripts/prove_autopick_s3_export_connectivity.py
```

Naturaleza:

* manual,
* explícito,
* no scheduler,
* no cron,
* no background worker,
* no runtime loop.

---

# Requisitos previos

## Variables esperadas

```env
AWS_REGION=sa-east-1
AUTO_PICK_EXPORT_S3_BUCKET=crypto-saas-data-ap
AUTO_PICK_EXPORT_S3_PREFIX=autopick/exports
AUTO_PICK_EXPORT_S3_ENCRYPTION=AES256
```

## Credenciales AWS

Esperadas vía:

```env
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
```

Opcional:

```env
AWS_SESSION_TOKEN
```

---

# IAM mínimo esperado

Permisos mínimos:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:HeadObject"
      ],
      "Resource": "arn:aws:s3:::crypto-saas-data-ap/autopick/exports/*"
    }
  ]
}
```

NO incluir:

* DeleteObject
* ListBucket
* PutBucketPolicy
* Admin permissions
* wildcard bucket permissions

---

# Artifact esperado

El script escribirá un artifact pequeño controlado.

Path esperado:

```text
s3://crypto-saas-data-ap/autopick/exports/connectivity-proof/<timestamp>.jsonl
```

Contenido:

```json
{"connectivity":"ok"}
```

---

# Verificaciones obligatorias

## 1. Upload exitoso

Debe completarse:

```text
put_object
```

---

## 2. Encryption contract

Debe enviarse:

```text
ServerSideEncryption=AES256
```

---

## 3. Metadata checksum

Debe persistirse:

```text
sha256
```

---

## 4. head_object exitoso

Debe resolverse:

```text
head_object
```

---

## 5. ContentLength

Debe coincidir exactamente.

---

## 6. checksum remoto

Debe coincidir exactamente.

---

# Boundary fail-closed esperado

El script debe abortar si:

* falta bucket,
* falta región,
* faltan credenciales,
* IAM denegado,
* metadata ausente,
* checksum mismatch,
* size mismatch,
* encryption inválida,
* key inválida,
* timeout,
* excepción boto3.

Nunca continuar parcialmente.

---

# Fuera de scope explícito

NO implementar:

* scheduler export,
* retries,
* retention,
* purge,
* replay analytics,
* runtime orchestration,
* production automation,
* background workers,
* multipart upload,
* KMS,
* broker/runtime coupling,
* trading execution.

---

# Resultado esperado

Al finalizar correctamente:

```text
AWS real connectivity proof successful
```

con:

* bucket,
* key,
* checksum,
* bytes,
* region,
* encryption,
* metadata verification.

---

# Riesgo principal siguiente

Después del connectivity proof, el siguiente riesgo real ya no es S3 substrate.

Será:

```text
credential governance
```

y posteriormente:

```text
controlled operationalization
```

antes de cualquier scheduler o automatización.

