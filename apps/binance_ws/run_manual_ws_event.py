from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.binance_ws.controlled_user_data_listener import process_user_data_messages
from apps.api.app.services.binance_fill_db import persist_binance_fills_db


# ⚠️ SOLO PARA USO MANUAL CONTROLADO
# - NO loop
# - NO scheduler
# - NO listener automático
# - 1 evento o pocos


def run_manual_event():
    import os

    database_url = os.environ.get("DATABASE_URL_RENDER")
    if not database_url:
        raise RuntimeError("DATABASE_URL_RENDER no definida")

    engine = create_engine(database_url)
    SessionLocal = sessionmaker(bind=engine)

    # ⚠️ PEGA AQUÍ 1 EVENTO REAL (executionReport)
    payload = {
        "event": {
            "e": "executionReport",
            "x": "TRADE",
            "X": "FILLED",
            "i": 61330568137,
            "t": 6268132893,
            "l": "0.00008000",
            "L": "78272.37000000",
            "Z": "6.26178960",
            "n": "0.00000762",
            "N": "BNB",
            "T": 1777771535839,
            "s": "BTCUSDT",
            "S": "BUY",
        }
    }

    USER_ID = "manual_user"
    ACCOUNT_ID = "binance_main"

    session = SessionLocal()

    try:
        result = process_user_data_messages(
            db=session,
            messages=[payload],
            user_id=USER_ID,
            account_id=ACCOUNT_ID,
            persist_binance_fills_db_callable=persist_binance_fills_db,
            max_messages=1,
        )

        print("==== RESULT ====")
        print(result)

    finally:
        session.close()


if __name__ == "__main__":
    run_manual_event()
