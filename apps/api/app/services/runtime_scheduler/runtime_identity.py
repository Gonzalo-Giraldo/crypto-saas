from __future__ import annotations

import os
import socket
import uuid


def build_runtime_owner_id(
    *,
    scheduler_name: str,
) -> str:
    scheduler_value = str(scheduler_name or "").strip()

    if not scheduler_value:
        raise ValueError("scheduler_name_required")

    return f"{scheduler_value}-runtime"


def build_runtime_instance_id(
    *,
    scheduler_name: str,
) -> str:
    scheduler_value = str(scheduler_name or "").strip()

    if not scheduler_value:
        raise ValueError("scheduler_name_required")

    hostname = socket.gethostname().strip() or "unknown-host"
    pid = os.getpid()

    runtime_uuid = uuid.uuid4().hex

    return (
        f"{scheduler_value}:"
        f"{hostname}:"
        f"{pid}:"
        f"{runtime_uuid}"
    )
