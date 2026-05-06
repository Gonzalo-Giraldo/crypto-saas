import json
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.binance_ws.controlled_ws_batch_runner import run_controlled_ws_batch
from apps.api.app.services.binance_fill_db import persist_binance_fills_db


def load_jsonl(path: str):
    messages = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            messages.append(json.loads(line))
    return messages


def run_from_file():
    import os

    database_url = os.environ.get("DATABASE_URL_RENDER")
    if not database_url:
        raise RuntimeError("DATABASE_URL_RENDER no definida")

    file_path = "apps/binance_ws/sample_events.jsonl"

    if not Path(file_path).exists():
        raise RuntimeError(f"No existe archivo: {file_path}")

    engine = create_engine(database_url)
    SessionLocal = sessionmaker(bind=engine)

    messages = load_jsonl(file_path)

    USER_ID = "manual_user"
    ACCOUNT_ID = "binance_main"

    session = SessionLocal()

    try:
        result = run_controlled_ws_batch(
            db=session,
            messages=messages,
            user_id=USER_ID,
            account_id=ACCOUNT_ID,
            persist_binance_fills_db_callable=persist_binance_fills_db,
            max_messages=50,
        )

        print("==== BATCH RESULT ====")
        print(result)

    finally:
        session.close()


if __name__ == "__main__":
    run_from_file()
