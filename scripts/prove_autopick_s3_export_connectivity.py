from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from apps.api.app.core.config import settings
from apps.api.app.data_runtime.services.autopick_export_runner import (
    S3AutopickExportStorage,
    validate_s3_export_configuration,
)


def main() -> None:
    config = validate_s3_export_configuration(
        bucket=settings.AUTO_PICK_EXPORT_S3_BUCKET,
        prefix=settings.AUTO_PICK_EXPORT_S3_PREFIX,
        region=settings.AWS_REGION,
        encryption=settings.AUTO_PICK_EXPORT_S3_ENCRYPTION,
    )

    payload = {
        "connectivity": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    content = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ) + "\n"

    body = content.encode("utf-8")
    checksum = hashlib.sha256(body).hexdigest()

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    export_id = f"connectivity-proof-{timestamp}"

    storage = S3AutopickExportStorage(
        bucket=config["bucket"],
        prefix=f"{config['prefix']}/connectivity-proof",
        region=config["region"],
        encryption=config["encryption"],
    )

    result = storage.write_text_artifact(
        export_id=export_id,
        suffix=".jsonl",
        content=content,
    )

    print()
    print("AWS real connectivity proof successful")
    print("--------------------------------------")
    print(f"bucket:      {result['bucket']}")
    print(f"key:         {result['key']}")
    print(f"path:        {result['path']}")
    print(f"checksum:    {result['checksum']}")
    print(f"bytes:       {result['bytes']}")
    print(f"region:      {config['region']}")
    print(f"encryption:  {config['encryption']}")
    print()


if __name__ == "__main__":
    main()
