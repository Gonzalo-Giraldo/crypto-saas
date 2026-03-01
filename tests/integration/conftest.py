import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Force test config before importing app modules.
TEST_DB_PATH = Path(tempfile.gettempdir()) / "crypto_saas_integration_test.db"
if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["ENCRYPTION_KEY"] = "test-encryption-key"
os.environ["BINANCE_TESTNET_BASE_URL"] = "https://testnet.binance.vision"
os.environ["IBKR_BRIDGE_BASE_URL"] = ""
os.environ["RISK_PROFILE_MODEL2_EMAIL"] = "admin@test.com"
os.environ["RISK_PROFILE_LOOSE_EMAIL"] = "trader@test.com"
os.environ["DAILY_STOP"] = "3"
os.environ["MAX_TRADES"] = "5"
os.environ["ENFORCE_2FA_FOR_ADMINS"] = "false"
os.environ["ENFORCE_2FA_EMAILS"] = ""

from apps.api.app.main import app
from apps.api.app.core.security import get_password_hash
from apps.api.app.db.session import Base, SessionLocal, engine
from apps.api.app.models.user import User


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        db.add(
            User(
                email="admin@test.com",
                hashed_password=get_password_hash("AdminPass123!"),
                role="admin",
            )
        )
        db.add(
            User(
                email="trader@test.com",
                hashed_password=get_password_hash("TraderPass123!"),
                role="trader",
            )
        )
        db.add(
            User(
                email="trader2@test.com",
                hashed_password=get_password_hash("Trader2Pass123!"),
                role="trader",
            )
        )
        db.commit()
    finally:
        db.close()

    with TestClient(app) as tc:
        yield tc
